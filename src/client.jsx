import React from 'react';
import {hydrateRoot} from 'react-dom/client';
import {GasApp,Seal} from './app.jsx';
if(window.GAS_IMPACT)hydrateRoot(document.getElementById('app'),<GasApp {...window.GAS_IMPACT}/>);
else if(document.getElementById('seal-root'))hydrateRoot(document.getElementById('seal-root'),<Seal labels={window.GAS_LABELS}/>);
