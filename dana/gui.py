import os,sys,time,shutil,subprocess,sqlite3
from pathlib import Path
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import *
ROOT=Path(__file__).resolve().parents[1]
CSS="QWidget{background:#0b1220;color:#eef4ff;font-family:Segoe UI} QPushButton{background:#16243b;border:1px solid #29405f;border-radius:12px;padding:11px;text-align:left} QPushButton:checked,QPushButton:hover{background:#1d4ed8} QLineEdit,QTextEdit,QSpinBox,QComboBox,QListWidget{background:#0b1527;border:1px solid #29405f;border-radius:10px;padding:8px} QFrame{border:1px solid #20314d;border-radius:16px}"
class Dana(QMainWindow):
 def __init__(self):
  super().__init__();self.setWindowTitle("Dana");self.resize(1100,700);self.proc=None;self.started=0
  root=QWidget();self.setCentralWidget(root);h=QHBoxLayout(root);h.setContentsMargins(0,0,0,0);side=QWidget();side.setFixedWidth(220);sl=QVBoxLayout(side);sl.addWidget(QLabel("<h2>DANA</h2><span style=\"color:#8fa2bf\">MCP Control Center</span>"));self.stack=QStackedWidget();g=QButtonGroup(self)
  for i,n in enumerate(["Dashboard","Connection","Access","Analytics","Tools","Logs"]):
   b=QPushButton(n);b.setCheckable(True);b.clicked.connect(lambda _,x=i:self.stack.setCurrentIndex(x));g.addButton(b);sl.addWidget(b);b.setChecked(i==0)
  sl.addStretch();h.addWidget(side);h.addWidget(self.stack,1)
  for f in [self.dashboard,self.connection,self.access,self.analytics,self.tools,self.logs]:self.stack.addWidget(f())
  self.t=QTimer(self);self.t.timeout.connect(self.refresh);self.t.start(1000);self.load_paths()
 def page(self,title,sub):
  w=QWidget();l=QVBoxLayout(w);l.setContentsMargins(34,28,34,28);l.addWidget(QLabel(f"<h1>{title}</h1><span style=\"color:#8fa2bf\">{sub}</span>"));return w,l
 def dashboard(self):
  w,l=self.page("Dashboard","Dana server, connector and live status");r=QHBoxLayout();self.status=QLabel("Offline");self.uptime=QLabel("—");self.workers=QLabel("5");self.mode=QLabel("Local")
  for n,v in [("STATUS",self.status),("MODE",self.mode),("UPTIME",self.uptime),("WORKERS",self.workers)]:c=QFrame();q=QVBoxLayout(c);q.addWidget(QLabel(n));v.setStyleSheet("font-size:22px;font-weight:700");q.addWidget(v);r.addWidget(c)
  l.addLayout(r);l.addWidget(QLabel("Connector URL"));self.url=QLineEdit();self.url.setReadOnly(True);l.addWidget(self.url);cp=QPushButton("Copy Connector URL");cp.clicked.connect(lambda:QApplication.clipboard().setText(self.url.text()));l.addWidget(cp);x=QHBoxLayout();s=QPushButton("Start Dana");s.clicked.connect(self.start);z=QPushButton("Stop Dana");z.clicked.connect(self.stop);x.addWidget(s);x.addWidget(z);l.addLayout(x);l.addStretch();return w
 def connection(self):
  w,l=self.page("Connection","Workers, port and Tailscale Funnel");self.port=QSpinBox();self.port.setRange(1024,65535);self.port.setValue(int(self.env().get("DANA_PORT","8765")));self.wc=QSpinBox();self.wc.setRange(1,128);self.wc.setValue(int(self.env().get("DANA_WORKERS","5")));self.ex=QComboBox();self.ex.addItems(["Tailscale Funnel","Local only"]);
  for n,x in [("Backend port",self.port),("Workers",self.wc),("Exposure",self.ex)]:l.addWidget(QLabel(n));l.addWidget(x)
  b=QPushButton("Save configuration");b.clicked.connect(self.save_cfg);l.addWidget(b);l.addStretch();return w
 def access(self):
  w,l=self.page("Access control","Allowed paths; empty means unrestricted");self.paths=QTextEdit();l.addWidget(self.paths);b=QPushButton("Save allowed paths");b.clicked.connect(self.save_paths);l.addWidget(b);return w
 def analytics(self):
  w,l=self.page("Token & time analytics","Live totals from Dana analytics");self.a=QLabel("Tokens: 0\nOperations: 0\nOperation time: 0s\nSession time: —");self.a.setStyleSheet("font-size:18px");l.addWidget(self.a);l.addStretch();return w
 def tools(self):
  w,l=self.page("Tools","All major Dana capabilities");q=QListWidget();q.addItems(["System & filesystem","Access policy","Agent & planning","Web / browser","Testing & quality","Debugging","PDF & Word (Persian/RTL)","Ruff / isort formatting","Codebase memory","Context optimization","Documentation context","Token & time analytics","Tailscale Funnel"]);l.addWidget(q);return w
 def logs(self):
  w,l=self.page("Logs","Live Dana output");self.log=QTextEdit();self.log.setReadOnly(True);l.addWidget(self.log);return w
 def env(self):
  d={};p=ROOT/".env"
  if p.exists():
   for x in p.read_text().splitlines():
    if "=" in x and not x.startswith("#"):k,v=x.split("=",1);d[k]=v
  return d
 def saveenv(self,d): (ROOT/".env").write_text("\n".join(f"{k}={v}" for k,v in d.items())+"\n")
 def save_cfg(self):
  d=self.env();d["DANA_PORT"]=str(self.port.value());d["DANA_WORKERS"]=str(self.wc.value());self.saveenv(d)
 def load_paths(self):self.paths.setPlainText("\n".join(filter(None,self.env().get("DANA_ALLOWED_PATHS","").split(";"))))
 def save_paths(self):
  d=self.env();d["DANA_ALLOWED_PATHS"]=";".join(x.strip() for x in self.paths.toPlainText().splitlines() if x.strip());self.saveenv(d)
 def start(self):
  if self.proc and self.proc.poll() is None:return
  e=os.environ.copy();e.update(self.env());e["DANA_PORT"]=str(self.port.value());e["DANA_WORKERS"]=str(self.wc.value());py=ROOT/(".venv/Scripts/python.exe" if os.name=="nt" else ".venv/bin/python");self.proc=subprocess.Popen([str(py if py.exists() else sys.executable),"-m","dana.main"],cwd=ROOT,env=e,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);self.started=time.time();QTimer.singleShot(1500,self.funnel)
 def funnel(self):
  if not self.proc or self.proc.poll() is not None:return
  if self.ex.currentText()=="Tailscale Funnel" and shutil.which("tailscale"):
   try:subprocess.run(["tailscale","funnel","--bg",f"http://127.0.0.1:{self.port.value()}"],check=True);out=subprocess.run(["tailscale","funnel","status"],capture_output=True,text=True).stdout;host=next((x for x in out.split() if x.startswith("https://")),"");self.url.setText(host.rstrip("/")+"/mcp")
   except Exception as e:self.log.append(str(e))
  else:self.url.setText(f"http://127.0.0.1:{self.port.value()}/mcp")
 def stop(self):
  if self.proc and self.proc.poll() is None:self.proc.terminate()
  self.started=0
 def refresh(self):
  run=bool(self.proc and self.proc.poll() is None);self.status.setText("Online" if run else "Offline");self.uptime.setText(f"{int(time.time()-self.started)}s" if run else "—");self.workers.setText(str(getattr(self,"wc",QSpinBox()).value() if hasattr(self,"wc") else 5));db=ROOT/".dana"/"analytics.db"
  if db.exists():
   try:c=sqlite3.connect(db);r=c.execute("SELECT COALESCE(SUM(total_tokens),0),COUNT(*),COALESCE(SUM(duration),0) FROM events").fetchone();c.close();self.a.setText(f"Tokens: {r[0]}\nOperations: {r[1]}\nOperation time: {r[2]:.2f}s\nSession time: {self.uptime.text()}")
   except Exception:pass
def main():
 app=QApplication(sys.argv);app.setStyleSheet(CSS);w=Dana();w.show();return app.exec()
if __name__=="__main__":raise SystemExit(main())
