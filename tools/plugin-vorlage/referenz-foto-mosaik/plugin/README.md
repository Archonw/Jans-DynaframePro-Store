# Foto Mosaik

A DynaFrame scene that rebuilds one of your photos from hundreds of your own
small photos, then slowly zooms into single tiles.

## What it shows

1. A photo appears, and tiles from your other photos settle over it in a
   wave until the whole picture is a mosaic.
2. The camera glides slowly towards one tile. Up close it turns into the real
   photo, with its date and place.
3. **Classic**: the camera glides back and the mosaic fades to the original.
   **Tour**: in, out, a short pause (adjustable), then the next tile of the same
   mosaic; after a set number of tiles the next motif follows (0 = stay).
   **Endless**: the camera dives into the tile until it fills the screen; that
   photo becomes the next mosaic.

Tiles are matched by colour (four areas per tile, in Lab colour space), the
same photo never sits next to itself, and an adjustable tint plus a faint
overlay of the original keep the motif recognisable.

## Where the photos come from

- **All photos in DynaFrame** (media library and media folders, plus extra
  folders you enter), **chosen DynaFrame folders** or **chosen DynaFrame
  playlists** (tick as many as you like), or **Immich** (all photos or
  the albums you tick, shared ones too; needs the server address and an API
  key with `asset.read`, `asset.view`, `album.read`). Immich photos can be
  limited like a smart album: favourites, minimum stars, orientation, people,
  city/state/country, on this day, last N days or a date range, camera make,
  model and lens, description, text in the image, file name, only photos with
  people, only camera photos, no screenshots, only photos in no album, minimum
  megapixels and file size, and albums, tags or file names to leave out.
  Archived photos are left out unless you allow them, hidden and locked photos
  are never used.
- **Your own photo as motif**: upload one or more photos on the plugin page
  (source "My own photos, uploaded here"); they are rebuilt from the tiles in
  turn. In endless mode the camera dives into a tile, shows that photo and then
  returns to one of your own photos.
- Tiles and motifs can come from different sources, e.g. tiles from the whole
  library and motifs from a "Best of" playlist.
- Photos stored in WebDAV (e.g. Nextcloud): DynaFrame only hands plugins a
  small preview. For motifs and the zoomed tile in full resolution, enter the
  WebDAV address, user and an app password on the plugin page; the plugin then
  loads the original itself. Without it, DynaFrame's own WebDAV cache is used
  when the original is there, otherwise the preview.

## Light on the Pi

The plugin prepares the tiles once in the background (small 96 px squares,
kept between runs, only new photos are opened) and packs them into a few
large sheets. For each motif it sends the picture in screen size and the
colours per grid cell; the scene does the matching itself in small steps
while the previous picture is still on screen.

## Setup

1. Install the package from the store.
2. Plugins > Foto Mosaik > Open Foto Mosaik: pick where the tiles and
   motifs come from. The first run takes a few minutes.
3. Press "Create playlist" (or add the scene "Foto Mosaik" to any playlist).
   About 5 minutes per playlist entry show several motifs.
