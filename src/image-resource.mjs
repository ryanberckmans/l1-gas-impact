export function createImageResource(url,{timeoutMs=15000,createImage=()=>new Image()}={}){
  let snapshot={phase:'idle'},pending=null,attempt=0;
  const listeners=new Set();
  const publish=value=>{snapshot=value;for(const listener of listeners)listener(value);};
  function load({retry=false}={}){
    if(snapshot.phase==='ready')return Promise.resolve(snapshot.image);
    if(pending)return pending;
    if(snapshot.phase==='error'&&!retry)return Promise.reject(snapshot.error);
    const current=++attempt,image=createImage();
    let resolve,reject,settled=false;
    pending=new Promise((accept,decline)=>{resolve=accept;reject=decline;});
    const operation=pending;
    const finish=error=>{
      if(settled||current!==attempt)return;
      settled=true;clearTimeout(timer);image.onload=image.onerror=null;
      pending=null;
      if(error){publish({phase:'error',error});reject(error);}
      else{publish({phase:'ready',image});resolve(image);}
    };
    const timer=setTimeout(()=>finish(new Error('Image loading timed out')),timeoutMs);
    image.onerror=()=>finish(new Error('Image loading failed'));
    image.onload=()=>Promise.resolve().then(()=>image.decode?.()).then(()=>finish(),finish);
    publish({phase:'loading'});
    try{image.src=url;}catch(error){finish(error);}
    return operation;
  }
  return {load,getSnapshot:()=>snapshot,subscribe:listener=>{listeners.add(listener);return()=>listeners.delete(listener);}};
}
