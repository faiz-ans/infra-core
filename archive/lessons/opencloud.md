# OpenCloud: homes as spaces, same tree as SMB

Working state when `site.data.access.web` is `opencloud`. SET produces it. Do not SSH a fix onto the host.

Each user home (`/users/<name>`) is that user's personal space. Each group home (`/groups/<group>`, and everyone is in `all`) is a project space under Spaces. The home root only lists. Immediate children (`files`, `photos`, and any other child such as `media`) are the writable subroots. Writes from SMB and from OpenCloud land in the same directories and follow the same rule. A folder created in an open OpenCloud view shows up without a manual refresh.

The Docker-era notes under `archive/bootstrap` bind `users/<name>/files` as the personal space and a shared project onto `shared/files`. Leave that layout alone.

## What SET runs

`ansible/playbooks/set.yml` runs identity before quadlets. Host directories for OpenCloud are created before the container. Directory provision and access run after quadlets. The "OpenCloud spaces" play runs after that, on workload hosts, whenever `site_plan.policy.web == opencloud`. It is not fingerprint-gated, so it runs on every SET. The record-applied play is after it: a spaces failure does not stamp fingerprints.

Day-2 SET skips a section whose fingerprint matches `applied.json`.

- Editing `components/opencloud/opencloud.container` or `components/caddy/Caddyfile` dirties the quadlets fingerprint (it hashes the component tree) and restarts those containers.
- Editing only `ansible/roles/opencloud/tasks/spaces.yml` does not need a fingerprint bump.
- The user-home ACL loop is part of the directory fingerprint, token `"directory": "posix-v13"` in `ansible/lib/diff.py`. A homes or keeper change has to bump that token or the next SET will skip it.

## Binds

`components/opencloud/opencloud.container`. Posix driver, root `/posix`, `STORAGE_USERS_POSIX_WATCH_FS=true`, `STORAGE_USERS_FILEMETADATA_CACHE_TTL=1s`. Templates:

- personal: `users/{{.User.Username}}`
- general: `groups/{{.SpaceName}}`

Mounts, host path then container path:

- `${appdata}/opencloud/posix` → `/posix`
- site users root → `/posix/users`
- `${appdata}/opencloud/projects` → `/posix/projects`
- site groups root → `/posix/groups`
- `${appdata}/opencloud/data` → `/var/lib/opencloud`

The container is rootless with `keep_id`. Container uid 1000 is the workload user on the host. Host uid 0 appears as 65534 inside the container. The process command is `opencloud init || true; opencloud server`. IDM is `${appdata}/opencloud/data/idm/idm.boltdb`.

`STORAGE_USERS_FILEMETADATA_CACHE_TTL` appears once. `OC_CACHE_STORE=noop` is shared with the ID cache. Leave it unset.

## Space identity

`ansible/lib/opencloud_spaces.py`, copied by the spaces role to `/usr/local/lib/site/opencloud_spaces.py` and run against `/var/lib/site/opencloud-spaces.json`. Homes are matched by directory name. SET creates a home only when it is missing. `files` and `photos` are created when missing. Other existing children are subroots too. Do not invent `media`.

A home with no space xattrs is attached and scanned. Grants that name some other account are replaced with the current account, and the old `user.oc.grant.*` key is removed, without a scan. A home whose space identity and grants are already right is not rewritten, and `user.oc.mtime` stays put. An empty member list does not wipe grants.

Space xattrs on the home inode (`user.oc.id` equals `user.oc.space.id`):

- personal: `user.oc.space.type=personal`, alias `personal/<username>`
- project: `user.oc.space.type=project`, alias `project/<group>`
- owner id is that same space id, owner type `spaceowner`, owner idp empty
- `user.oc.propagation=1`, `user.oc.type=2`

A child that is still its own space root is demoted: space, owner, grant, and quota xattrs are dropped, and `user.oc.parentid` is set to the home's space id.

The OpenCloud user id comes from `openCloudUUID` on the user entry in the IDM bolt (`uid=<name>,ou=users`). Group membership records store the group's id in the same DN, so the uuid has to come from the user entry. A site user with no IDM record is skipped. Their home is attached on the SET after they have signed in once. Admin basic auth as `admin` returns HTTP 500 (`missing claim 'name'`). There is no Graph user-create in this product.

Indexes live under `${appdata}/opencloud/posix/indexes` (`by-user-id/<uuid>.mpk`, `by-type/personal.mpk`, `by-type/project.mpk`). The spaces role also moves a personal space that OpenCloud created on `users/<name>/files` up onto the home, and drops stale `personal.mpk` entries from that older root.

Scan only the container paths the library prints (`scan /posix/...`). A home that already has a space id does not need `opencloud posixfs scan`. Scanning `/posix/users/<name>/files` or `/posix/groups/all` walks a large library. `posixfs scan` also `setxattr`s `user.oc.dirty`. That fails with `EPERM` on a sticky directory, and on a tree the workload user cannot write.

## Grants

Offload attribute `user.oc.grant.u:<uuid>` or `user.oc.grant.g:<gid>`. Value is `0x00` then `t=A:f=<flags>:p=<letters>:c=:e=0\n`. Group grants include `f=g`. The offload limit is 1024 bytes.

Letters (`pkg/storage/utils/ace/ace.go`, case-sensitive `strings.Contains`):

| Letter | Effect |
| --- | --- |
| `t` | Stat, GetPath |
| `x` | ListContainer |
| `r` | download, list, stat. With `w`, also Move |
| `w` | InitiateFileUpload. Move only when `r` is also set |
| `a` | CreateContainer |
| `d` | Delete |
| `u` | ListRecycle |
| `U` | RestoreRecycleItem |
| `q` | GetQuota |
| `C` | AddGrant (share). Not used here |

`w` without `r` does not set Move. PermissionWrite (WebDAV `N`, and `W` on a file) needs `w` and `U`. PermissionCreate (WebDAV `CK` on a directory) needs `a` and `w`. PermissionDelete is `d`. PermissionRead needs list, recycle list, stat, path, quota, and download. Missing `u` falls through to SecureViewer, and the WebDAV string is only `X`. The role name is RoleEditor only when share (`C`) is present. Without `C` the name is RoleLegacy, and the OCS flags (`CK`, `D`, `NV`) are still set. Leave `C` off.

Home roots get `txruq`. Every immediate child, and everything inside it, gets `txrwaduUq`. The subroot itself carries `d` and `U` so a folder created directly in it inherits delete and rename on the first listing. Deeper creates inherit from the parent directory immediately.

ACE flags other than `g` are not implemented ("no inheritance yet"). An inherit-only (`i`) grant does nothing. A deny returns early and discards allows already accumulated, so a deny on an ancestor blocks the whole subtree.

Permission checks walk `user.oc.parentid`, not the directory that contains the folder (`pkg/storage/pkg/decomposedfs/node/permissions.go`). If a child of a subroot still has the home's space id as `parentid`, the walk never sees the editor grant and the UI offers no write actions. `_reparent` sets `parentid` of each direct child of a subroot to that subroot's id when it currently equals the space id. Deeper nodes are already parented at their real parent. This is a directory-name walk. It does not read file contents.

`UserIDEqual` compares the opaque id only. Type is ignored. If `user.oc.owner.id` is the person's OpenCloud uuid, every node returns OwnerPermissions: create, delete, and move on the home root as well. The owner stays the space id.

CreateDir checks CreateContainer on the parent only. Delete checks Delete on the node. Move checks Move on the source and, for a directory, CreateContainer on the destination. Renaming a subroot in place fails because the destination parent is the home (`txruq`, no `a`). Moving a subroot into another subroot can succeed, because that destination has `a` and `w`+`r` sets Move. Delete of a subroot succeeds while the node has `d`. The UI and Caddy hide those actions. The grant stays.

## POSIX and SMB

Home root is `0750` `root:root`. The person (or the group) has `rx`. The workload user has `rwx`, including a default ACL, so OpenCloud can `setxattr` `user.oc.dirty` and create children. Subroots are `2770`, setgid, ACL `rwx` plus a default ACL, owned by the user (or `root:<group>`). The ACL loop covers every immediate child, skipping `.oc-*`, not only `files` and `photos`. `chmod -t` clears sticky under those children.

Sticky (`S_ISVTX`) makes `setxattr` of `user.*` return `EPERM` for anyone but the owner, even with an `rwx` ACL. Leave sticky off the home and the subroots.

Samba (`ansible/roles/samba/tasks/main.yml`) publishes `[users]` and `[groups]` only. `unix extensions = no`, `smb3 unix extensions = no`, `inherit acls = yes`, `force directory mode = 2770`. With unix extensions left on, a Mac creates mode `0755` and the ACL mask stays `mask::---`, so the other side cannot enter.

OpenCloud mkdir is `os.MkdirAll(path, 0700)`. The default ACL is inherited and the creation mode then zeros the mask. The keeper puts the mask back.

## Keeper

`/usr/local/sbin/site-access-mask`, unit `site-access-mask.service`, installed from `ansible/roles/directory/tasks/homes.yml` when SMB or OpenCloud is the access engine. fanotify marks the users and groups filesystems (`FAN_CREATE | FAN_MOVED_TO | FAN_ONDIR | FAN_ATTRIB`). The mark has to be the filesystem that contains the path. A resolver that accepts `/` from the users mount drops `/groups`.

`ensure` restores the ACL mask and copies the parent's named default ACL when it did not stick, then stamps the editor grant. The stamp runs only at depth >= 3 (inside a subroot, not on the subroot). It copies each `user.oc.grant.u:` / `g:` key from the subroot and writes `txrwaduUq`. Watch calls `ensure` immediately. `scan_one` runs 0.5s later and calls `opencloud posixfs scan` only when `user.oc.id` is missing, after copying `user.oc.space.id` from the nearest ancestor that has `user.oc.space.alias`.

fanotify `CREATE` is a notification after the syscall, not a permission event. There is no `FAN_CREATE_PERM`, so the keeper cannot block mkdir. A folder created directly in a subroot used to be listed before the stamp, so Rename and Delete were missing until a later refetch. Putting `txrwaduUq` on the subroot itself makes the create response include `D` and `N`. The keeper remains for folders the stamp still has to correct, and for the ACL mask.

`repair` walks directory names under subroots. It does not read file bytes. The next SET that restarts the unit runs it.

Mac Finder creates a temp directory named `.::TMPNAME:D:<numbers>%<numbers>:untitled folder` and then renames it. Assimilation of that temp path fails (`user.oc.space.id` missing after the rename). The final name then logs `skip already known item` on both user and group trees. That log is `_errSkipAlreadyKnown` in reva `pkg/storage/fs/posix/tree/assimilation.go` when the node id is set, the cached path matches, and the metadata mtime matches. It is not why only one tree updates live.

## Context menus

WebDAV `oc:permissions` is not the ACE string. The UI checks `indexOf`: create `CK`, delete `D`, rename `N`.

At path `/` in a project space, `currentFolder` is the Space object. `Space.canCreate` in the shipped web client is hardcoded `return!0`, and a Space has no permissions string, so the group home root still offered New Folder after the API denied it. Personal homes keep the WebDAV resource, so the list grant is enough to hide New Folder there. The overlay in `ansible/roles/opencloud/tasks/spaces.yml` changes that one `canCreate` to `return!1`.

The files app (`web-app-files-<hash>.site3.mjs`) gates the FAB, the New Folder item, create-folder, and the shortcut on `permissions.includes('CK')`.

`Space.canUpload` returns true for a personal space when `user.id === owner.id`. The Personal nav item used to require `isOwner(user)`. The owner is the space id, so the link disappeared. The overlay shows Personal when a personal space exists, and does not treat the signed-in user as the owner. Setting `user.oc.owner.id` back to the user uuid would restore `isOwner` and would also make the home root writable.

Delete, rename, and move-to are hidden when the resource path has fewer than two segments. The path is space-relative: `/spaces/<id>/files` becomes `/files` (one segment, a subroot). `/files/New` is two segments. A one-segment child is a layout folder (`files`, `photos`, `media`) and must not offer Rename, Delete, or Move.

`replace_one` in that task bails out when the new string is already present and the old string is gone. The old string must not be a prefix of the new one, or the next SET inserts the patch again.

## Caddy

`components/caddy/Caddyfile`, site `https://cloud.{$DOMAIN}`:

```
@webjs path /js/*
header @webjs {
    Cache-Control no-cache
    defer
}
@layout {
    method DELETE MOVE
    path_regexp layout ^/(?:remote\.php/)?dav/spaces/[^/]+/[^/]+/?$
}
respond @layout 403
```

`respond` is before `reverse_proxy` in Caddy's order, so a one-segment DELETE or MOVE (the subroot) is refused and deeper paths still proxy. A `handle` around `@layout` would swallow every DELETE and MOVE. Space ids can contain `$`. The query string is not part of the path.

`flush_interval -1` and the long timeouts stay. They are what keep SSE and TUS unbuffered.

## Web assets and cache

OpenCloud serves the web UI from `$BaseDataPath/web/assets/core`, which is `${appdata}/opencloud/data/web/assets/core`. FallbackFS prefers a file in that directory over the embedded asset. `index.html` is no-cache and gets exactly one `<base href="/"/>` at serve time. Strip that tag before writing the overlay. Saving the served HTML writes the base back, and the next serve inserts a second one. `html.Render` can reformat the page, so rewrite `index.html` only when a script reference actually changes.

Other static files, including hashed `.mjs`, are `max-age=604800`. Last-Modified is the process start time, not the file mtime. A changed file at the same URL stays in the browser for 7 days. Publish a new filename (`.site3.mjs`, `.site.mjs`) and point `index.html` at it. Caddy `@webjs` no-cache covers `/js/*` after that, and the new name is what beats a copy already cached.

The files-app overlay is `web-app-files-<hash>.site3.mjs`. The shell overlay that re-lists personal folders is `index.html-<hash>.site.mjs`, referenced from the script tag `./js/index.html-<hash>.mjs`. Grant or asset changes restart `opencloud.service` because the posix driver does not watch `setxattr`. The overlay itself is read on the next request. Reload the browser after that SET.

## SMB writes in an open folder

`services/clientlog` sends `folder-created`, `file-touched`, and `item-moved` to `GetSpaceMembers` (`pkg/utils/grpc.go`):

- `personal`: only `space.Owner.Id.OpaqueId`
- `project`: the grantees

The personal owner opaque id is the space id, so the signed-in user never receives the event. A refresh works, because the listing read is fine and the metadata cache is 1s. A project space notifies the grantee, which is why `/groups/all/files` updates on its own.

Changing the personal space to type `project` would notify grantees and would also take the home out of Personal. `Space.canUpload` and the nav item both key off `driveType===personal`. Leave the type as `personal`.

The shell overlay re-lists the open personal folder every 2s (`driveType===personal`, `webdav.listFiles` on `currentFolder.path`). It upserts a child whose id, etag, size, mdate, or name changed, and removes a child only after it has been missing from two listings, so a folder just created in OpenCloud is not dropped by a stale PROPFIND. Project spaces are left to SSE. The guard is `window.__sitePersonalWatch`, so a second init does not start another timer.

## Checked, and not the remaining gap

These were already true while personal folders still needed a refresh. Leave them.

- `STORAGE_USERS_POSIX_WATCH_FS=true` and the 1s metadata TTL. A refresh shows the SMB write, so the read path works. The missing piece was the push.
- `skip already known item` on the final Finder name. It is logged for user trees and group trees.
- The keeper's editor stamp. It fixes grants. It does not address the event to the signed-in user.
- Sticky, unix extensions, and the ACL mask. Those were the earlier "SMB create is invisible or inaccessible" failures. They are fixed in the product above.

## What SET installs

- Posix root, watch, 1s metadata cache, personal template on the home, general template on the group home. Users and groups trees bind over `/posix`.
- `opencloud_spaces.py`: space on the home inode, owner is the space, list grant `txruq` on the home, editor grant `txrwaduUq` on each subroot and inside it, `parentid` of a subroot's children pointed at the subroot, IDM uuid from the user entry, scan only a home that was just attached.
- Home `rx` for the person or group, workload user `rwx`, subroots `2770` with ACL and default ACL, sticky cleared. `files` and `photos` created if missing.
- Samba: `[users]` and `[groups]`, unix extensions off, directory mode `2770`, inherit ACLs.
- `site-access-mask`: mask and editor stamp on creates inside a subroot, scan only a node that has no `user.oc.id`.
- Web overlay: New Folder hidden without `CK`, Personal nav without `isOwner`, rename/delete/move hidden on a one-segment path, personal folders re-listed while open. New script names so the 7-day cache does not keep the old file.
- Caddy: `/js/*` revalidated, one-segment DELETE/MOVE of a subroot refused, SSE/TUS unbuffered.
