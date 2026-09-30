import React,{useEffect,useRef,useState} from 'react';

export function Seal({labels}){
  const [ready,setReady]=useState(false),[open,setOpen]=useState(false);
  const trigger=useRef(null),viewer=useRef(null);
  useEffect(()=>{setReady(true);},[]);
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
    <button ref={trigger} type="button" className="seal-button" disabled={!ready} aria-label={labels.viewImage} title={labels.viewImage} onClick={()=>setOpen(true)}>
      <img src="/assets/seal-32.png" srcSet="/assets/seal-32.png 1x, /assets/seal-64.png 2x, /assets/seal-96.png 3x, /assets/seal-128.png 4x" width="32" height="32" alt="" fetchPriority="low"/>
    </button>
    {open&&<dialog ref={viewer} className="seal-viewer" aria-label={labels.viewImage} onClose={()=>setOpen(false)} onKeyDown={e=>{if(e.key==='Tab'){e.preventDefault();viewer.current.querySelector('button')?.focus();}}} onClick={e=>{if(e.target===e.currentTarget)setOpen(false);}}>
      <button type="button" className="seal-close" autoFocus onClick={()=>setOpen(false)}>{labels.closeImage}</button><img src="/assets/seal.png" width="1254" height="1254" alt=""/>
    </dialog>}
  </>;
}
