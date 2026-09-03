# Windows desktop installation

Şiirden Karelere is an installable Progressive Web App. Microsoft Edge places it
alongside normal Windows applications and opens it in a dedicated window. The
Python server and Instagram credential remain on the deployed host.

## Install it

1. Deploy the current source and note its permanent HTTPS service URL.
2. Open that URL in Microsoft Edge.
3. Sign in with the application password if login protection is enabled.
4. Select **Bilgisayara yükle** at the top of the application.
5. Confirm **Yükle** (Install) in Edge.
6. Enable **Masaüstü kısayolu oluştur** if a desktop shortcut is wanted. Start
   menu and taskbar pinning are optional.
7. Close the browser and open **Şiirden Karelere** from the new shortcut to test it.

If the in-app install action is not visible, use Edge's **…** menu and choose
**More tools → Apps → Install this site as an app**. To repair a shortcut later,
open `edge://apps`, choose the application's details, and select
**Create Desktop shortcut**.

## Behavior and safety

- The installed app continues to use the same HTTPS service URL.
- New server deployments appear automatically; there is no `.exe` to update.
- A successful login is remembered for 30 days by default.
- Only the static interface shell and branded icons are cached locally. Poems,
  photos, rendered media, login responses, and API responses are not cached by
  the service worker.
- Publishing requires an internet connection and is never queued offline.

To remove or repair the installation, open `edge://apps`. Uninstalling the PWA
does not delete the Cloud Run service or affect the Instagram account.
