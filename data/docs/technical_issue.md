# Cloudnest Technical Troubleshooting

## Sync Failures
File sync failures are most commonly caused by a file name containing a
character unsupported on the destination OS (e.g. a colon `:` in a filename
syncing to Windows). The Cloudnest desktop client logs these under
"Sync Errors" in the app, and the fix is to rename the offending file.

## Upload Stuck at 0%
If an upload is stuck at 0% for more than 2 minutes, this is usually a
firewall or proxy blocking the upload endpoint. Ask the customer to try on
a different network (e.g. mobile hotspot) to confirm, then check if their
network admin needs to allowlist `upload.cloudnest.example`.

## Storage Quota Miscalculation
Storage usage shown in the app can lag up to 1 hour behind actual usage due
to caching. If a customer reports incorrect storage numbers, ask them to
force-refresh via Settings > Storage > Recalculate before escalating as a
bug.

## Mobile App Crashes on Launch
Crashes on launch are almost always fixed by clearing the app's local cache
(Settings > Storage > Clear Cache on the device) rather than reinstalling,
since reinstalling does not clear the corrupted local sync database.
