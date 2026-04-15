This directory where I store scripts to inference and evalutate models.

### !!! NOTES
If you use wget to download the release (include models).
You should create a PAT on GitHub then add flag `--header="Authorization: token YOUR_TOKEN"` to wget command in scripts [Setup](tools/deploy-model/setup.sh).
You must install the dataset dependency.

### If you do not want to use wget to get release. Use SSH.
1. Download models on your host (from: Release [FP32](https://github.com/BeginnerCoder52/FSS/releases/download/v0.1.0-alpha/best_float32.tflite) and [INT8](https://github.com/BeginnerCoder52/FSS/releases/download/v0.1.0-alpha/best_int8.tflite) or **OneDrive `FSS\4. SOFTWARE ENGINEERING\temp\models`**). Then copy 2 models to the Pi 4B in folder `fss-test/models` (You should use `scp` to copy through ssh).
2. Download dataset on your host (from OneDrive `FSS\4. SOFTWARE ENGINEERING\temp\test-images`). Then copy to the Pi 4B in folder `fss-test/test-images`.
3. Run `setup.sh`. Then reboot.
4. Run `setup_python.sh`.
5. Run `python test-inference.py`.
