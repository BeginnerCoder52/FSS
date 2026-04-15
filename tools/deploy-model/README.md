This directory contains scripts to run **inference** and **evaluation** for models on a Raspberry Pi 4B.

## Notes
- The setup scripts may download model artifacts from **GitHub Releases**.
- If you use `wget` to download release assets (including models), you may need a **GitHub Personal Access Token (PAT)** to avoid rate limits or to access private assets.
  - Create a PAT and provide it to `wget` via a header:
    `--header="Authorization: token YOUR_TOKEN"`
  - **Do not commit tokens** to the repository. Prefer exporting it as an environment variable (e.g. `GITHUB_TOKEN`) and using that in scripts.
- You must install dataset dependencies before running evaluation.

## Download models & dataset on host, then copy via SSH
### 1) Download models on your host
Download from GitHub Release:
- FP32: https://github.com/BeginnerCoder52/FSS/releases/download/v0.1.0-alpha/best_float32.tflite
- INT8: https://github.com/BeginnerCoder52/FSS/releases/download/v0.1.0-alpha/best_int8.tflite

(**Internal alternative**: OneDrive `FSS\4. SOFTWARE ENGINEERING\temp\models`)

### 2) Copy models to the Pi
Copy both `.tflite` files to the Pi folder:
- Destination on Pi: `fss-test/models`

Example (PATH BASED-ON YOUR ENV):
```bash
scp best_float32.tflite best_int8.tflite pi@192.168.2.2:~/fss-test/models/
```

### 3) Download dataset on your host and copy to the Pi
(**Internal source**: OneDrive `FSS\4. SOFTWARE ENGINEERING\temp\test-images`)

Copy to:
- Destination on Pi: `fss-test/test-images`

Example:
```bash
scp -r test-images pi@192.168.2.2:~/fss-test/
```

### 4) Run setup scripts on the Pi
```bash
./setup.sh
sudo reboot
```

After reboot:
```bash
./setup_python.sh
python tools/deploy-model/test-inference.py
```
