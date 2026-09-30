import React,{useEffect,useRef,useState} from 'react';
import {createImageResource} from './image-resource.mjs';

const master=createImageResource('/assets/seal.png');
const thumbnails={src:'/assets/seal-32.png',srcSet:'/assets/seal-32.png 1x, /assets/seal-64.png 2x, /assets/seal-96.png 3x, /assets/seal-128.png 4x'};

export function Seal({labels}){
  const [ready,setReady]=useState(false),[open,setOpen]=useState(false);
  const [imageState,setImageState]=useState(master.getSnapshot);
  const trigger=useRef(null),viewer=useRef(null),closeButton=useRef(null);
  useEffect(()=>{setReady(true);setImageState(master.getSnapshot());return master.subscribe(setImageState);},[]);
  const preload=()=>{
    if(navigator.connection?.saveData)return;
    master.load().catch(()=>{});
  };
  const activate=()=>{setOpen(true);master.load({retry:true}).catch(()=>{});};
  useEffect(()=>{
    if(!open)return;
    const dialog=viewer.current,overflow=document.body.style.overflow;
    document.body.style.overflow='hidden';
    if(!dialog.open)dialog.showModal();
    return()=>{
      dialog.close();
      document.body.style.overflow=overflow;
      trigger.current?.focus({preventScroll:true});
    };
  },[open]);
  return <>
    <button ref={trigger} type="button" className="seal-button" disabled={!ready} aria-label={labels.viewImage} title={labels.viewImage} onClick={activate} onMouseEnter={()=>{if(matchMedia('(hover: hover) and (pointer: fine)').matches)preload();}} onFocus={e=>{if(e.currentTarget.matches(':focus-visible'))preload();}}>
      <img {...thumbnails} width="32" height="32" alt="" fetchPriority="low"/>
    </button>
    {open&&<dialog ref={viewer} className="seal-viewer" aria-label={labels.viewImage} onClose={()=>setOpen(false)} onCancel={()=>setOpen(false)} onKeyDown={e=>{
      if(e.key!=='Tab')return;
      const buttons=Array.from(viewer.current.querySelectorAll('button:not(:disabled)'));
      const first=buttons[0],last=buttons.at(-1);
      if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}
      else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}
    }} onClick={e=>{if(e.target===e.currentTarget)setOpen(false);}}>
      <button ref={closeButton} type="button" className="seal-close" autoFocus onClick={()=>setOpen(false)}>{labels.closeImage}</button>
      <div className="seal-content">
        {imageState.phase==='ready'?<img src="/assets/seal.png" width="1254" height="1254" alt=""/>:<img {...thumbnails} className="seal-preview" width="1254" height="1254" alt=""/>}
        <div className="seal-status" role="status" aria-live="polite" aria-atomic="true">
          {imageState.phase==='loading'&&<><span className="image-loading-indicator" aria-hidden="true"/>{labels.loadingImage}</>}
          {imageState.phase==='error'&&labels.imageLoadFailed}
        </div>
        {imageState.phase==='error'&&<button className="image-retry" type="button" onClick={()=>{closeButton.current?.focus();master.load({retry:true}).catch(()=>{});}}>{labels.retryImage}</button>}
      </div>
    </dialog>}
  </>;
}
