// One native video timeline built from reusable, progressively fetched fragments.
export function createSegmentPlayer(video, manifest, fetchStream, failed) {
  const media=new MediaSource(),url=URL.createObjectURL(media);
  let disposed=false;const readers=new Set(),pending=new Set();
  const check=()=>{if(disposed)throw new DOMException('Player disposed','AbortError');};
  function operation(buffer,action) {
    check();return new Promise((resolve,reject)=>{
      const finish=error=>{buffer.removeEventListener('updateend',done);buffer.removeEventListener('error',bad);pending.delete(cancel);error?reject(error):resolve();};
      const done=()=>finish(),bad=()=>finish(new Error('Could not append preview media'));
      const cancel=()=>finish(new DOMException('Player disposed','AbortError'));
      pending.add(cancel);buffer.addEventListener('updateend',done,{once:true});buffer.addEventListener('error',bad,{once:true});
      try{action();}catch(error){finish(error);}
    });
  }
  async function append(buffer,path) {
    const response=await fetchStream(path);check();
    if(!response.ok)throw new Error('Preview fragment unavailable');
    if(!response.body?.getReader){const bytes=await response.arrayBuffer();await operation(buffer,()=>buffer.appendBuffer(bytes));return;}
    const reader=response.body.getReader();readers.add(reader);
    try {
      while(!disposed){const {value,done}=await reader.read();if(done)break;if(value?.byteLength)await operation(buffer,()=>buffer.appendBuffer(value));}
    } finally {readers.delete(reader);try{reader.releaseLock();}catch{}}
  }
  const opened=async()=>{
    try {
      check();media.duration=manifest.duration;
      const picture=media.addSourceBuffer(manifest.video_mime),sound=media.addSourceBuffer(manifest.audio_mime);
      sound.appendWindowEnd=manifest.duration;
      const audio=append(sound,manifest.audio.path);
      const images=(async()=>{
        let offset=0;
        for(const segment of manifest.videos){
          check();picture.timestampOffset=offset;
          // Move the old end first: the next start equals the previous end,
          // which browsers reject while that old append window is still set.
          picture.appendWindowEnd=Infinity;picture.appendWindowStart=offset;picture.appendWindowEnd=offset+segment.duration;
          await append(picture,segment.path);offset+=segment.duration;
        }
      })();
      await Promise.all([images,audio]);check();
      if(media.readyState==='open'){media.duration=manifest.duration;media.endOfStream();}
    }catch(error){if(!disposed)failed(error);}
  };
  media.addEventListener('sourceopen',opened,{once:true});
  video.src=url;video.preload='auto';video.load();
  return {dispose(){
    disposed=true;media.removeEventListener('sourceopen',opened);
    for(const cancel of [...pending])cancel();
    for(const reader of readers)void reader.cancel().catch(()=>{});
    readers.clear();URL.revokeObjectURL(url);
  }};
}
