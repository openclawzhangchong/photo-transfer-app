# -*- coding: utf-8 -*-
"""
批量手机电脑传照片
===================
局域网图片上传服务 + 系统托盘。

功能：
- 启动后在本机 8080 端口跑一个 HTTP 服务
- 手机/电脑在局域网访问 http://<IP>:8080 即可扫码、拍照、批量上传图片
- 图片按顺序 1.jpg 2.jpg ... 保存到「保存目录」
- 系统托盘图标显示状态，可 启动/停止服务、打开浏览器、选择保存目录、重置编号、退出

作者：openclawzhangchong
许可证：MIT
"""

import json
import os
import re
import socket
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    import pystray
    from PIL import Image, ImageDraw
except Exception:
    pystray = None

# ---------------- 配置 ----------------
PORT = 8080
MAX_FILES = 100
CONFIG_PATH = Path(os.path.join(os.path.expanduser("~"), ".photo_transfer.json"))
APP_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.ico")


def default_save_dir() -> Path:
    return Path(os.path.join(str(Path.home()), "Desktop", "上传图片"))


def load_config() -> dict:
    cfg = {"save_dir": str(default_save_dir()), "port": PORT}
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                cfg.update({k: data[k] for k in cfg if k in data})
    except Exception:
        pass
    return cfg


def save_config(cfg: dict) -> None:
    try:
        CONFIG_PATH.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


CFG = load_config()
SAVE_DIR = Path(CFG["save_dir"])
SAVE_DIR.mkdir(parents=True, exist_ok=True)


def get_next_index() -> int:
    try:
        return len([f for f in SAVE_DIR.iterdir() if f.is_file()]) + 1
    except Exception:
        return 1


next_index = [get_next_index()]
index_lock = threading.Lock()


# ---------------- HTML 前端 ----------------
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>图片上传</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;display:flex;flex-direction:column;align-items:center;padding:16px}
h1{margin:12px 0 6px;font-size:1.3em}
.url-box{background:#1e293b;border:2px solid #334155;border-radius:12px;padding:10px 18px;margin:6px 0;text-align:center;max-width:380px;width:100%}
.url-box .label{font-size:.75em;color:#94a3b8;margin-bottom:3px}
.url-box .url{font-size:1em;font-family:monospace;color:#38bdf8;word-break:break-all}
#qr{margin:6px 0}#qr img{width:140px;height:140px;border-radius:8px}
.counter{font-size:1.1em;font-weight:700;margin:6px 0;color:#38bdf8}
.tabs{display:flex;margin:8px 0;background:#1e293b;border-radius:10px;overflow:hidden;width:100%;max-width:380px}
.tab{flex:1;text-align:center;padding:10px 0;font-size:.95em;cursor:pointer;color:#94a3b8;transition:.15s}
.tab.active{background:#38bdf8;color:#0f172a;font-weight:700}
.cam-panel{display:none;flex-direction:column;align-items:center;gap:12px;width:100%;max-width:380px}
.cam-panel.show{display:flex}
.shutter{width:80px;height:80px;border-radius:50%;border:5px solid #38bdf8;background:rgba(56,189,248,.15);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:2em;transition:.15s;-webkit-tap-highlight-color:transparent}
.shutter:active{background:#38bdf8;transform:scale(.92)}
.cam-hint{font-size:.85em;color:#94a3b8}
.cam-preview{display:none;width:100%;border-radius:12px;max-height:280px;object-fit:cover}
.cam-confirm{display:none;flex-direction:row;gap:12px}
.cam-confirm.show{display:flex}
.cam-btn{padding:12px 24px;border-radius:10px;border:none;font-size:1em;font-weight:600;cursor:pointer}
.cam-btn.ok{background:#22c55e;color:#0f172a}
.cam-btn.ok:active{background:#4ade80}
.cam-btn.no{background:#475569;color:#e2e8f0}
.cam-btn.no:active{background:#64748b}
.file-panel{display:none;flex-direction:column;align-items:center;gap:8px;width:100%;max-width:380px}
.file-panel.show{display:flex}
.drop{border:3px dashed #334155;border-radius:16px;padding:22px;text-align:center;cursor:pointer;transition:.2s;width:100%}
.drop:hover{border-color:#38bdf8}
.drop .ic{font-size:2.2em;margin-bottom:4px}
.drop p{color:#94a3b8;font-size:.85em}
input[type=file]{display:none}
.btn{background:#38bdf8;color:#0f172a;border:none;border-radius:8px;padding:10px 28px;font-size:1em;font-weight:600;cursor:pointer;transition:.2s}
.btn:disabled{background:#475569;color:#94a3b8;cursor:not-allowed}
.progress{margin:8px 0;text-align:center;width:100%;max-width:380px}
.pbar{height:6px;background:#1e293b;border-radius:3px;overflow:hidden;margin-top:4px}
.pfill{height:100%;background:#38bdf8;width:0%;transition:width .3s;border-radius:3px}
.status{margin-top:8px;padding:10px 14px;background:#1e293b;border-radius:10px;text-align:center;font-size:.85em;max-width:380px;width:100%;min-height:36px}
.status.ok{border:1px solid #22c55e;color:#4ade80}
.status.err{border:1px solid #ef4444;color:#f87171}
.thumbs{display:grid;grid-template-columns:repeat(5,1fr);gap:3px;margin:8px 0;width:100%;max-width:380px}
.thumb{width:100%;aspect-ratio:1;border-radius:5px;object-fit:cover;background:#1e293b}
.info{font-size:.7em;color:#64748b;margin-top:6px}
</style>
</head>
<body>
<h1>📷 图片上传</h1>
<div class="url-box"><div class="label">手机扫码或输入地址</div><div class="url" id="url-d"></div></div>
<div id="qr"><img id="qr-img"></div>
<div class="counter" id="counter">已上传 0 / 100</div>

<div class="tabs">
  <div class="tab active" id="tc" onclick="sw('cam')">📷 拍照</div>
  <div class="tab" id="tf" onclick="sw('file')">📁 选文件</div>
</div>

<div class="cam-panel show" id="cp">
  <input type="file" id="cam-input" accept="image/*" capture="environment">
  <div class="shutter" id="shutter" title="拍照">📸</div>
  <div class="cam-hint">点击拍照 → 确认 → 自动上传</div>
  <img class="cam-preview" id="cam-pv">
  <div class="cam-confirm" id="cam-act">
    <button class="cam-btn no" id="cam-no">🔄 重拍</button>
    <button class="cam-btn ok" id="cam-ok">✅ 确认上传</button>
  </div>
</div>

<div class="file-panel" id="fp">
  <div class="drop" id="dz"><div class="ic">🖼️</div><p>点击选择或拖拽图片</p><p style="font-size:.75em;margin-top:3px;color:#64748b">最多100张 JPG/PNG/HEIC/WEBP</p></div>
  <input type="file" id="fi" multiple accept="image/*,.heic,.heif">
  <button class="btn" id="ub" disabled>上传所选图片</button>
</div>

<div class="progress" id="pw" style="display:none"><span id="pt">0/0</span><div class="pbar"><div class="pfill" id="pf"></div></div></div>
<div class="status" id="st"></div>
<div class="thumbs" id="th"></div>
<p class="info">按顺序保存为 1.jpg, 2.jpg, 3.jpg ...</p>

<script>
(function(){
  var u=location.href;
  document.getElementById('url-d').textContent=u;
  var q=document.getElementById('qr-img');
  q.src='https://api.qrserver.com/v1/create-qr-code/?size=140x140&data='+encodeURIComponent(u);
  q.onerror=function(){document.getElementById('qr').style.display='none'};
})();
function sw(t){
  document.getElementById('tc').className='tab'+(t==='cam'?' active':'');
  document.getElementById('tf').className='tab'+(t==='file'?' active':'');
  document.getElementById('cp').className='cam-panel'+(t==='cam'?' show':'');
  document.getElementById('fp').className='file-panel'+(t==='file'?' show':'');
}
var camIn=document.getElementById('cam-input');
var camPv=document.getElementById('cam-pv');
var camAct=document.getElementById('cam-act');
var camFile=null;
document.getElementById('shutter').addEventListener('click',function(){camIn.click()});
document.getElementById('cam-no').addEventListener('click',function(){
  camFile=null;camIn.value='';camPv.style.display='none';camAct.className='cam-confirm';
});
document.getElementById('cam-ok').addEventListener('click',async function(){
  if(!camFile)return;
  var fd=new FormData();fd.append('files',camFile,'shot.jpg');
  try{
    var r=await fetch('/upload',{method:'POST',body:fd});
    var d=await r.json();
    if(d.success){show('ok','✅ 第 '+d.total+' 张已保存');upCnt(d.total);addTh(camFile);}
    else throw new Error(d.message||'fail');
  }catch(e){show('err','上传失败: '+e.message);}
  camFile=null;camIn.value='';camPv.style.display='none';camAct.className='cam-confirm';
});
camIn.addEventListener('change',function(){
  if(camIn.files.length){
    camFile=camIn.files[0];
    camPv.src=URL.createObjectURL(camFile);
    camPv.style.display='block';
    camAct.className='cam-confirm show';
  }
});
var dz=document.getElementById('dz');
var fi=document.getElementById('fi');
var ub=document.getElementById('ub');
var sel=[];
dz.addEventListener('click',function(){fi.click()});
dz.addEventListener('dragover',function(e){e.preventDefault();dz.style.borderColor='#38bdf8'});
dz.addEventListener('dragleave',function(){dz.style.borderColor='#334155'});
dz.addEventListener('drop',function(e){e.preventDefault();dz.style.borderColor='#334155';af(e.dataTransfer.files)});
fi.addEventListener('change',function(){af(fi.files);fi.value=''});
function af(fs){
  var imgs=Array.from(fs).filter(function(f){return f.type.startsWith('image/')||/\.(heic|heif|jpg|jpeg|png|webp|bmp|gif)$/i.test(f.name)});
  var room=100-sel.length;
  if(room<=0){show('err','已达上限');return}
  sel.push.apply(sel,imgs.slice(0,room));
  show('','已选 '+sel.length+' 张');
  ub.disabled=!sel.length;ub.textContent='上传 '+sel.length+' 张';
}
ub.addEventListener('click',async function(){
  if(!sel.length)return;
  ub.disabled=true;
  var pw=document.getElementById('pw'),pt=document.getElementById('pt'),pf=document.getElementById('pf');
  pw.style.display='block';var done=0,err=0,tot=sel.length;
  for(var i=0;i<tot;i+=5){
    var b=sel.slice(i,i+5),fd=new FormData();b.forEach(function(f){fd.append('files',f)});
    try{var r=await fetch('/upload',{method:'POST',body:fd});var d=await r.json();if(d.success)upCnt(d.total);else throw 0}
    catch(e){err+=b.length}
    done+=b.length;pt.textContent=done+'/'+tot;pf.style.width=(done/tot*100)+'%';
  }
  show(err?'err':'ok',err?'⚠️ '+err+'张失败':'✅ '+tot+'张全部完成');
  sel=[];ub.disabled=true;ub.textContent='上传所选图片';
  setTimeout(function(){pw.style.display='none'},1500);
});
function show(c,m){var el=document.getElementById('st');el.className='status'+(c?' '+c:'');el.textContent=m}
function upCnt(n){document.getElementById('counter').textContent='已上传 '+n+' / 100'}
function addTh(f){var i=document.createElement('img');i.className='thumb';i.src=URL.createObjectURL(f);document.getElementById('th').appendChild(i)}
fetch('/status').then(function(r){return r.json()}).then(function(d){upCnt(d.count)}).catch(function(){});
</script>
</body>
</html>"""


# ---------------- HTTP 服务 ----------------
class UploadHandler(BaseHTTPRequestHandler):
    server_version = "PhotoTransfer/1.0"

    def log_message(self, fmt, *args):
        pass  # 静默

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_PAGE.encode("utf-8"))
        elif self.path == "/status":
            with index_lock:
                count = next_index[0] - 1
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"count": count}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path != "/upload":
            self.send_response(404)
            self.end_headers()
            return
        ct = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ct:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": False}).encode())
            return
        boundary = ct.split("boundary=")[1].encode()
        body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        saved = 0
        for part in body.split(b"--" + boundary)[1:]:
            if part.strip() in (b"--", b""):
                continue
            he = part.find(b"\r\n\r\n")
            if he == -1:
                continue
            header = part[:he].decode("utf-8", errors="replace")
            data = part[he + 4:]
            if data.endswith(b"\r\n"):
                data = data[:-2]
            fn = re.search(r'filename="([^"]+)"', header)
            if not fn:
                continue
            orig = fn.group(1)
            with index_lock:
                idx = next_index[0]
                if idx > MAX_FILES:
                    continue
                next_index[0] = idx + 1
            ext = Path(orig).suffix.lower() or ".jpg"
            dest = SAVE_DIR / f"{idx}{ext}"
            dest.write_bytes(data)
            saved += 1
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"success": saved > 0, "saved": saved, "total": next_index[0] - 1}).encode())


def get_lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LAN_IP = get_lan_ip()


# ---------------- 托盘图标（运行时生成） ----------------
def build_icon_image(running: bool) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # 圆角背景
    color = (56, 189, 248, 255) if running else (100, 116, 139, 255)
    d.rounded_rectangle([4, 4, 60, 60], radius=14, fill=color)
    # 相机镜头
    d.ellipse([18, 16, 46, 44], fill=(15, 23, 42, 255))
    d.ellipse([24, 22, 40, 38], fill=color)
    d.ellipse([28, 26, 36, 34], fill=(15, 23, 42, 255))
    # 状态点
    dot = (34, 197, 94, 255) if running else (239, 68, 68, 255)
    d.ellipse([44, 38, 58, 52], fill=dot)
    d.rounded_rectangle([44, 38, 58, 52], radius=7, outline=(255, 255, 255, 255), width=1)
    return img


# ---------------- 服务控制 ----------------
server = None
server_lock = threading.Lock()
server_running = {"on": False}


def start_server() -> bool:
    global server
    with server_lock:
        if server is not None:
            return True
        try:
            server = ThreadingHTTPServer(("0.0.0.0", CFG["port"]), UploadHandler)
        except OSError as e:
            print("无法绑定端口:", e)
            return False
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        server_running["on"] = True
        return True


def stop_server() -> None:
    global server
    with server_lock:
        if server is not None:
            server.shutdown()
            server.server_close()
            server = None
        server_running["on"] = False


def refresh_index() -> None:
    with index_lock:
        next_index[0] = get_next_index()


# ---------------- 托盘逻辑 ----------------
def _open_browser():
    webbrowser.open(f"http://127.0.0.1:{CFG['port']}")


def _pick_dir(icon=None, item=None):
    global SAVE_DIR
    try:
        from tkinter import Tk, filedialog

        root = Tk()
        root.withdraw()
        root.update()
        chosen = filedialog.askdirectory(initialdir=str(SAVE_DIR))
        root.destroy()
        if chosen:
            new_dir = Path(chosen)
            new_dir.mkdir(parents=True, exist_ok=True)
            SAVE_DIR = new_dir
            CFG["save_dir"] = str(new_dir)
            save_config(CFG)
            refresh_index()
            if icon:
                icon.notify(f"保存目录已改为:\n{new_dir}")
    except Exception as e:
        if icon:
            icon.notify(f"选择目录失败: {e}")


def _reset(icon=None, item=None):
    refresh_index()
    if icon:
        icon.notify(f"编号已重置为 {next_index[0]}")


def _open_save_dir(icon=None, item=None):
    try:
        os.startfile(str(SAVE_DIR))
    except Exception as e:
        if icon:
            icon.notify(f"无法打开目录: {e}")


def _toggle(icon=None, item=None):
    if server_running["on"]:
        stop_server()
        icon.notify(f"服务已停止")
    else:
        if start_server():
            icon.notify(
                f"服务已启动\n局域网: http://{LAN_IP}:{CFG['port']}\n本机: http://127.0.0.1:{CFG['port']}"
            )
        else:
            icon.notify("端口被占用，无法启动服务")


def _quit(icon=None, item=None):
    stop_server()
    if icon:
        icon.stop()
    os._exit(0)


def main() -> None:
    global SAVE_DIR
    save_dir = Path(CFG["save_dir"])
    if not save_dir.exists():
        save_dir = default_save_dir()
        save_dir.mkdir(parents=True, exist_ok=True)
        CFG["save_dir"] = str(save_dir)
        save_config(CFG)
    SAVE_DIR = save_dir
    refresh_index()

    if not start_server():
        print(f"端口 {CFG['port']} 被占用，服务未启动")

    if pystray is not None:
        image = build_icon_image(server_running["on"])
        menu = pystray.Menu(
            pystray.Menu.Item("▶ 启动/停止服务", _toggle, enabled=True),
            pystray.Menu.Item("打开浏览器", _open_browser, enabled=True),
            pystray.Menu.Item("选择保存目录…", _pick_dir, enabled=True),
            pystray.Menu.Item("打开保存目录", _open_save_dir, enabled=True),
            pystray.Menu.Item("重置编号", _reset, enabled=True),
            pystray.Menu.Sep(),
            pystray.Menu.Item("退出", _quit, enabled=True),
        )
        tooltip = f"批量手机电脑传照片\nhttp://{LAN_IP}:{CFG['port']}\n已保存 {next_index[0]-1} 张"
        icon = pystray.Icon("PhotoTransfer", image, tooltip, menu)

        # 周期性刷新 tooltip
        stop_flag = threading.Event()

        def refresh_loop():
            while not stop_flag.wait(10):
                try:
                    n = next_index[0] - 1
                    running = "运行中" if server_running["on"] else "已停止"
                    icon.title = f"批量手机电脑传照片 | {running} | 已保存 {n} 张 | {LAN_IP}:{CFG['port']}"
                except Exception:
                    pass

        threading.Thread(target=refresh_loop, daemon=True).start()
        icon.run()
        stop_flag.set()
    else:
        # 无托盘依赖时退化为前台服务
        print("=" * 50)
        print(f"  [OK] 图片上传服务已启动")
        print(f"  保存目录: {SAVE_DIR}")
        print(f"  本机: http://127.0.0.1:{CFG['port']}")
        print(f"  局域网: http://{LAN_IP}:{CFG['port']}")
        print("按 Ctrl+C 停止")
        print("=" * 50)
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_server()
            print("\n服务已停止")


if __name__ == "__main__":
    main()
