"""Pinned, integrity-checked optional H3 upscaler acquisition."""
import hashlib,os,tempfile,threading,urllib.request
from pathlib import Path

AUTO_H3='Auto Download H3 Upscaler'
MODEL_NAME='minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors'
MODEL_URL='https://huggingface.co/LBH-123-AI/Minimax_h3_latent_Upscaler/resolve/main/minimax_h3_latent_upscaler_3d_conv_v1/'+MODEL_NAME
MODEL_SHA256='4f57821f5837f32f7142b67d815606dbd7550f194e5c769f7d6c3f83b146a5e6'
EXPECTED_BYTES=690_592_992
_LOCK=threading.RLock()
_VERIFIED={}


def ensure_h3_upscaler(root=None,progress=None):
    if root is None:
        import folder_paths
        root=Path(folder_paths.models_dir)/'latent_upscale_models'
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    path=root/MODEL_NAME
    def verify(file):
        if file.stat().st_size!=EXPECTED_BYTES:raise ValueError('H3 upscaler size verification failed.')
        with file.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=MODEL_SHA256:raise ValueError('H3 upscaler SHA256 verification failed.')
    with _LOCK:
        if path.exists():
            stat=path.stat();identity=(stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns)
            if _VERIFIED.get(str(path.resolve()))!=identity:verify(path);_VERIFIED[str(path.resolve())]=identity
            return MODEL_NAME
        fd,temp=tempfile.mkstemp(prefix='.h3-download-',suffix='.part',dir=root);os.close(fd)
        try:
            received=0
            with urllib.request.urlopen(urllib.request.Request(MODEL_URL,headers={'User-Agent':'MiniMaxH3Director'}),timeout=60) as src,open(temp,'wb') as dst:
                while chunk:=src.read(1024**2):
                    try:
                        import comfy.model_management as manager
                        manager.throw_exception_if_processing_interrupted()
                    except ImportError:pass
                    received+=len(chunk)
                    if received>EXPECTED_BYTES:raise ValueError('H3 upscaler download exceeds its pinned size.')
                    dst.write(chunk)
                    if progress:progress(received,EXPECTED_BYTES)
                dst.flush();os.fsync(dst.fileno())
            verify(Path(temp));os.replace(temp,path)
            return MODEL_NAME
        finally:
            if os.path.exists(temp):os.unlink(temp)
