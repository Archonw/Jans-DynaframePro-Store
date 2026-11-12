# Living Photos depth server

Small HTTP service that computes depth maps for the DynaFrame plugin **Living Photos** on a stronger machine in your home network (e.g. Unraid). Model: Depth Anything V2 Small (Apache-2.0), ONNX export by fabio-sim.

## Start on Unraid (terminal or SSH)

```sh
docker run -d --name living-photos-depth --restart unless-stopped -p 8765:8765 -v /mnt/user/appdata/living-photos-depth:/data python:3.12-slim sh -c "pip install --no-cache-dir onnxruntime numpy pillow && python -c \"import urllib.request as u; u.urlretrieve('https://raw.githubusercontent.com/Archonw/Jans-DynaframePro-Store/main/plugin_packs/living-photos/depth-server/server.py', '/data/server.py')\" && python /data/server.py"
```

The first start downloads the Python packages and the model (about 250 MB). Then enter `http://<server IP>:8765` on the Living Photos plugin page and press "Test connection".

- `GET /health` – status, model, threads, average seconds per photo
- `POST /depth?size=518` with a JPEG – returns a grayscale PNG (bright = near)

Environment: `PORT` (8765), `DATA` (/data), `THREADS` (all cores).
