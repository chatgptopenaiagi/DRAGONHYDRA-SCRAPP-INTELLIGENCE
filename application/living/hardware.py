"""Real user-accessible measurements; no drivers or invented sensor values."""
import os,shutil,subprocess,time,threading
from pathlib import Path
from .contracts import now
class Hardware:
    def __init__(self,data):self.data=Path(data);self.lock=threading.Lock();self.last=None;self.cached=None;self.measured=0
    def sample(self):
        with self.lock:
            if self.cached and time.monotonic()-self.measured<2:return self.cached
            try:import psutil
            except ImportError:return {'status':'UNAVAILABLE','reason':'Optional system measurement module is unavailable','at':now()}
            started=time.monotonic();memory=psutil.virtual_memory();disk=shutil.disk_usage(self.data);cpu=psutil.cpu_percent(interval=.2);io=psutil.disk_io_counters();network=psutil.net_io_counters();processes=[];ports=[]
            own={os.getpid()}
            try:own.update(p.pid for p in psutil.Process().children(recursive=True))
            except psutil.Error:pass
            for p in psutil.process_iter(['pid','ppid','name','memory_info','cpu_times','create_time']):
                try:
                    d=p.info;name=d['name'].lower();role='APPLICATION_OWNED' if p.pid in own else 'DRAGONHYDRA_INSTANCE' if 'dragonhydra' in name else 'POSTGRESQL' if name in ('postgres.exe','pg_ctl.exe') else 'LOCAL_AI' if any(x in name for x in ('llama-server','qwen','ollama','blackhole')) else None
                    if not role:continue
                    processes.append({'pid':p.pid,'parent_pid':d['ppid'],'name':d['name'],'role':role,'rss_bytes':d['memory_info'].rss,'cpu_seconds':round(d['cpu_times'].user+d['cpu_times'].system,3),'started_epoch':d['create_time']})
                    try:ports.extend({'pid':p.pid,'address':x.laddr.ip,'port':x.laddr.port} for x in p.net_connections(kind='tcp') if x.status=='LISTEN')
                    except psutil.Error:pass
                except(psutil.Error,AttributeError):pass
            services=[]
            if hasattr(psutil,'win_service_iter'):
                for service in psutil.win_service_iter():
                    try:
                        name=service.name()
                        if name.lower().startswith('postgres'):services.append({'name':name,'state':service.status(),'pid':service.pid()})
                    except psutil.Error:pass
            gpu={'status':'UNAVAILABLE','reason':'NVIDIA-SMI unavailable or no permitted NVIDIA sensor'};exe=shutil.which('nvidia-smi')
            if exe:
                try:
                    r=subprocess.run([exe,'--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                    rows=[]
                    if r.returncode==0:
                        for line in r.stdout.strip().splitlines()[:8]:
                            fields=[x.strip() for x in line.split(',')]
                            if len(fields)!=5:continue
                            def number(x):
                                try:return float(x)
                                except ValueError:return None
                            rows.append(dict(zip(('name','utilization_percent','memory_used_mib','memory_total_mib','temperature_c'),[fields[0]]+[number(x) for x in fields[1:]])))
                    if rows:gpu={'status':'MEASURED','method':'NVIDIA-SMI','devices':rows}
                except (OSError,subprocess.TimeoutExpired):pass
            rates={};current={'time':time.monotonic(),'read':io.read_bytes if io else 0,'write':io.write_bytes if io else 0,'sent':network.bytes_sent,'received':network.bytes_recv}
            if self.last:
                dt=current['time']-self.last['time'];rates={k+'_bytes_per_second':max(0,(current[k]-self.last[k])/dt) for k in ('read','write','sent','received')};rates['interval_seconds']=dt
            self.last=current
            self.cached={'at':now(),'status':'MEASURED','cpu':{'utilization_percent':cpu,'sample_seconds':.2,'temperature':{'status':'UNAVAILABLE','reason':'No verified CPU package temperature sensor configured'}},'ram':{'total_bytes':memory.total,'used_bytes':memory.used,'available_bytes':memory.available,'percent':memory.percent},'disk':{'total_bytes':disk.total,'free_bytes':disk.free,'used_bytes':disk.used},'system_io_rates':rates or {'status':'FIRST_SAMPLE_NO_RATE'},'network_process_attribution':{'status':'UNAVAILABLE','note':'Network counters above are system-wide, not assigned to individual processes'},'gpu':gpu,'processes':processes,'listening_ports':ports,'postgresql_services':services,'measurement_seconds':time.monotonic()-started};self.measured=time.monotonic();return self.cached
