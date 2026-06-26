# #!/usr/bin/env python3
# """QR code generator: takes a URL string, outputs base64 PNG to stdout."""
# import sys, json, base64, io
# 
# try:
#     import qrcode
# except ImportError:
#     print(json.dumps({"type": "ERROR", "message": "qrcode package not installed"}), flush=True)
#     sys.exit(1)
# 
# def generate_qr(url: str, box_size: int = 10) -> str:
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_M,
#         box_size=box_size,
#         border=2,
#     )
#     qr.add_data(url)
#     qr.make(fit=True)
#     img = qr.make_image(fill_color="black", back_color="white")
#     buf = io.BytesIO()
#     img.save(buf, format="PNG")
#     return base64.b64encode(buf.getvalue()).decode("ascii")
# 
# if __name__ == "__main__":
#     line = sys.stdin.readline()
#     if not line:
#         print(json.dumps({"type": "ERROR", "message": "No input"}), flush=True)
#         sys.exit(1)
#     try:
#         msg = json.loads(line)
#         url = msg.get("url", "")
#         if not url:
#             print(json.dumps({"type": "ERROR", "message": "Missing 'url' field"}), flush=True)
#             sys.exit(1)
#         b64 = generate_qr(url, box_size=msg.get("box_size", 10))
#         print(json.dumps({"type": "QR_DATA", "base64": b64, "url": url}), flush=True)
#     except Exception as e:
#         print(json.dumps({"type": "ERROR", "message": str(e)}), flush=True)
#         sys.exit(1)
