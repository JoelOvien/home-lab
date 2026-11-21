# growatt-widget

A macOS desktop / Notification Center widget showing battery %, grid state
(with outage duration), load and solar from the `growatt-monitor` worker.

It reads the newest row of the D1 `snapshots` table and any open `outages`
row. It never talks to Growatt, so it can't trigger a login lockout. The
recorder writes every 5 minutes; the widget reloads about every 10 and turns
its timestamp orange once the data is more than 15 minutes old. Battery
charge/discharge direction isn't shown because the `batPower` sign is
unverified.

## Setup

1. Create a Cloudflare API token with **D1 Read** only (don't reuse the
   worker's token), then copy the example config and fill it in:

   ```bash
   cp Shared/Secrets.example.json Shared/Secrets.json
   ```

   `Secrets.json` is gitignored and gets bundled into the app at build time.

2. Build and install:

   ```bash
   xcodebuild -project GrowattWidget.xcodeproj -scheme GrowattWidget -configuration Release -derivedDataPath build build
   ```

   ```bash
   rm -rf /Applications/GrowattWidget.app && cp -R build/Build/Products/Release/GrowattWidget.app /Applications/
   ```

3. Open `/Applications/GrowattWidget.app` once. Its window shows the live
   status, which confirms the config works. Then right-click the desktop,
   choose **Edit Widgets**, search for **Growatt**, and add the small or
   medium size.

The project is signed to run locally (ad-hoc, no team). If the widget doesn't
show up in the gallery, open the project in Xcode, set a Team under Signing &
Capabilities for both targets (a free Apple ID works), and rebuild. To see
whether the system registered the extension:

```bash
pluginkit -m -p com.apple.widgetkit-extension | grep -i growatt
```

If the app window shows an authentication error, check the token has D1 Read
on the right account.
