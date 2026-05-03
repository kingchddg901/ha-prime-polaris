var $="ha-prime-polaris-card",H="0.5.2",P="grill",D={climate:"climate.{prefix}",chamber_temp:"sensor.{prefix}_chamber_temperature",running_status:"sensor.{prefix}_running_status",active_mode:"sensor.{prefix}_active_mode",active_smoke_level:"sensor.{prefix}_active_smoke_level",last_alarm:"sensor.{prefix}_last_alarm",probe_1_temp:"sensor.{prefix}_probe_1_temperature",probe_2_temp:"sensor.{prefix}_probe_2_temperature",probe_1_eta:"sensor.{prefix}_probe_1_eta",probe_2_eta:"sensor.{prefix}_probe_2_eta",setpoint:"number.{prefix}_temperature",smoke_level:"number.{prefix}_smoke_level",probe_1_target:"number.{prefix}_probe_1_target",probe_2_target:"number.{prefix}_probe_2_target",push_dedupe:"number.{prefix}_push_alert_dedupe",smoke_mode:"switch.{prefix}_smoke_mode",winter_mode:"switch.{prefix}_winter_mode",alarm:"switch.{prefix}_temperature_alarm",cook_session:"switch.{prefix}_cook_session",push_alerts:"switch.{prefix}_push_alerts",notes:"text.{prefix}_cook_notes",protein:"text.{prefix}_cook_protein",weight_lb:"text.{prefix}_cook_weight_lb",ambient_override:"text.{prefix}_cook_ambient_override",wind_override:"text.{prefix}_cook_wind_override",chamber_override:"text.{prefix}_chamber_override_entity",probe_1_override:"text.{prefix}_probe_1_override_entity",probe_2_override:"text.{prefix}_probe_2_override_entity"},S=4,B=3e4;var de=/^[a-z_]+\.[a-z0-9_]+$/;function F(i,e,t){let r={value:null,source:""};if(!i||!e)return r;if(de.test(e)){let n=i.states[e];if(!n)return{value:null,source:`${e} (missing)`};if(e.startsWith("weather.")&&n.attributes?.[t]!=null){let c=parseFloat(n.attributes[t]);return Number.isFinite(c)?{value:c,source:e}:r}let s=parseFloat(n.state);return Number.isFinite(s)?{value:s,source:e}:r}let o=parseFloat(e);return Number.isFinite(o)?{value:o,source:"literal"}:r}function W(i,e){if(!i)return null;let t=l=>D[l].replace("{prefix}",e),r=l=>i.states[t(l)]??null,o=l=>{let p=r(l);if(!p)return null;let u=parseFloat(p.state);return Number.isFinite(u)?u:null},n=l=>r(l)?.state==="on",s=l=>{let p=r(l);return p?p.state==="unknown"||p.state==="unavailable"?"":p.state:""},c=l=>{let p=r(l===1?"probe_1_eta":"probe_2_eta");if(!p)return{minutes:null,in_stall:!1,stdev:null,source:null};let u=parseFloat(p.state);return{minutes:Number.isFinite(u)?u:null,in_stall:!!p.attributes?.in_stall,stdev:p.attributes?.stall_stdev??null,source:p.attributes?.prior_source??null,samples:p.attributes?.samples??0}},d=r("climate"),m=o("setpoint")??d?.attributes?.temperature??null;return{prefix:e,entityIds:Object.fromEntries(Object.keys(D).map(l=>[l,t(l)])),chamber:o("chamber_temp")??d?.attributes?.current_temperature??null,setpoint:m,chamberDelta:o("chamber_temp")!=null&&m!=null?o("chamber_temp")-m:null,runningStatus:s("running_status")||null,activeMode:s("active_mode")||"off",smokeLevel:o("active_smoke_level"),smokeOn:n("smoke_mode"),winterOn:n("winter_mode"),alarmOn:n("alarm"),probe1:{temp:o("probe_1_temp"),target:o("probe_1_target"),override_raw:s("probe_1_override"),override_resolved:F(i,s("probe_1_override"),"temperature"),...c(1)},probe2:{temp:o("probe_2_temp"),target:o("probe_2_target"),override_raw:s("probe_2_override"),override_resolved:F(i,s("probe_2_override"),"temperature"),...c(2)},chamber_override:{raw:s("chamber_override"),resolved:F(i,s("chamber_override"),"temperature")},cookSession:n("cook_session"),notes:s("notes"),protein:s("protein"),weight_lb:s("weight_lb"),ambient:s("ambient_override"),wind:s("wind_override"),ambientResolved:F(i,s("ambient_override"),"temperature"),windResolved:F(i,s("wind_override"),"wind_speed"),pushOn:n("push_alerts"),pushDedupe:o("push_dedupe"),account:(()=>{let l=r("climate"),p=l?.attributes?.email??null,u=l?.attributes?.token_expiry??null,g=u?Math.max(0,Math.round((u*1e3-Date.now())/864e5)):null;return{email:p,daysToExpiry:g}})(),lastAlarm:(()=>{let l=r("last_alarm");return!l||l.state==="unknown"||l.state==="unavailable"||!l.state?null:{title:l.state,body:l.attributes?.body??"",captured_at:l.attributes?.captured_at??null,source:l.attributes?.source??null}})()}}function k(i,e){if(!i||!e)return{};let t=(r,o,n={})=>i.callService(r,o,n);return{setSetpoint:r=>t("number","set_value",{entity_id:e.entityIds.setpoint,value:r}),setSmokeLevel:r=>t("number","set_value",{entity_id:e.entityIds.smoke_level,value:r}),setProbeTarget:(r,o)=>t("number","set_value",{entity_id:e.entityIds[`probe_${r}_target`],value:o}),toggle:r=>{let o=e.entityIds[r],n=i.states[o]?.state==="on";return t("switch",n?"turn_off":"turn_on",{entity_id:o})},setText:(r,o)=>t("text","set_value",{entity_id:e.entityIds[r],value:o??""}),powerOff:()=>t("climate","set_hvac_mode",{entity_id:e.entityIds.climate,hvac_mode:"off"})}}var a={bg:"#0d1117",panel:"#161b22",panelBorder:"#30363d",text:"#e6edf3",textDim:"#8b949e",accent:"#fb923c",accentDim:"#9a3412",cool:"#3b82f6",hot:"#ef4444",steady:"#22c55e",smoke:"#a78bfa",alarm:"#f87171",stall:"#f59e0b",probe1:"#ef4444",probe2:"#06b6d4",chartChamber:"#fb923c",chartProbe1:"#ef4444",chartProbe2:"#06b6d4"},O=5;var q=`
  :host {
    display: block;
    color: ${a.text};
    font-family: var(--paper-font-body1_-_font-family, system-ui, sans-serif);
  }
  .card {
    background: ${a.bg};
    border-radius: 14px;
    padding: 16px;
    display: grid;
    gap: 12px;
  }
  .row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
  }
  .panel {
    background: ${a.panel};
    border: 1px solid ${a.panelBorder};
    border-radius: 10px;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .panel.tall { padding: 16px 14px; }
  .panel-label {
    font-size: 11px;
    color: ${a.textDim};
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  .big-temp {
    font-size: 44px;
    font-weight: 600;
    line-height: 1;
    margin-top: 2px;
  }
  .big-temp .unit {
    font-size: 22px;
    color: ${a.textDim};
    font-weight: 400;
    margin-left: 4px;
  }
  .big-temp.over   { color: ${a.hot}; }
  .big-temp.under  { color: ${a.cool}; }
  .big-temp.steady { color: ${a.steady}; }
  .delta {
    font-size: 13px;
    color: ${a.textDim};
    margin-top: 2px;
  }
  .chip-row {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }
  .chip {
    background: ${a.bg};
    border: 1px solid ${a.panelBorder};
    border-radius: 999px;
    padding: 3px 10px;
    font-size: 11px;
    color: ${a.textDim};
  }
  .chip.active   { border-color: ${a.accent}; color: ${a.accent}; }
  .chip.smoke    { border-color: ${a.smoke};  color: ${a.smoke};  }
  .chip.alarm    { border-color: ${a.alarm};  color: ${a.alarm};  }
  .chip.stall    { border-color: ${a.stall};  color: ${a.stall};  }

  .probe {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 8px 12px;
    align-items: center;
  }
  .probe-label { font-size: 11px; color: ${a.textDim}; text-transform: uppercase; }
  .probe-temp {
    font-size: 28px;
    font-weight: 600;
    line-height: 1;
  }
  .probe-target {
    font-size: 13px;
    color: ${a.textDim};
  }
  .probe-eta {
    font-size: 14px;
    color: ${a.text};
    margin-top: 2px;
  }
  .probe-eta.fitting { color: ${a.textDim}; font-style: italic; }
  .probe-eta.stall   { color: ${a.stall}; font-weight: 500; }

  .controls {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
    gap: 8px;
  }
  .recipe-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 8px;
  }
  .recipe-tile {
    background: ${a.bg};
    color: ${a.text};
    border: 1px solid ${a.panelBorder};
    border-radius: 10px;
    padding: 10px 12px;
    cursor: pointer;
    text-align: left;
    display: flex;
    flex-direction: column;
    gap: 2px;
    transition: border-color 0.15s, transform 0.05s;
  }
  .recipe-tile:hover { border-color: ${a.accent}; }
  .recipe-tile:active { transform: scale(0.98); }
  .recipe-name {
    font-size: 13px;
    font-weight: 600;
  }
  .recipe-desc {
    font-size: 11px;
    color: ${a.textDim};
    font-variant-numeric: tabular-nums;
  }
  .stepper-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
  }
  .stepper-label {
    font-size: 12px;
    color: ${a.textDim};
    text-transform: uppercase;
    letter-spacing: 0.04em;
    flex: 0 0 88px;
  }
  .stepper-input {
    background: ${a.bg};
    color: ${a.text};
    border: 1px solid ${a.panelBorder};
    border-radius: 6px;
    padding: 6px 8px;
    width: 80px;
    text-align: center;
    font-size: 16px;
    font-weight: 500;
    -moz-appearance: textfield;
  }
  .stepper-input::-webkit-outer-spin-button,
  .stepper-input::-webkit-inner-spin-button {
    -webkit-appearance: none;
    margin: 0;
  }
  .stepper-input:focus { outline: none; border-color: ${a.accent}; }
  .stepper-unit {
    font-size: 13px;
    color: ${a.textDim};
    min-width: 22px;
  }
  .stepper-btn {
    width: 36px;
    padding: 6px 0;
    font-size: 18px;
    font-weight: 600;
  }
  .slider {
    flex: 1;
    accent-color: ${a.accent};
    height: 6px;
  }
  .arc-panel {
    align-items: center;
  }
  .chamber-setpoint {
    margin: 4px auto 0;
    justify-content: center;
  }
  .chamber-setpoint .stepper-label { flex: 0 0 auto; }
  .arc-gauge {
    width: 100%;
    max-width: 260px;
    height: auto;
    display: block;
    margin: 4px auto 0;
    user-select: none;
    touch-action: none;
  }
  .arc-gauge text {
    font-family: var(--paper-font-body1_-_font-family, system-ui, sans-serif);
  }
  button.action {
    background: ${a.panel};
    color: ${a.text};
    border: 1px solid ${a.panelBorder};
    border-radius: 8px;
    padding: 8px 10px;
    cursor: pointer;
    font-size: 13px;
    transition: border-color 0.15s, background 0.15s;
  }
  button.action:hover { border-color: ${a.accent}; }
  button.action.on    { border-color: ${a.accent}; background: ${a.accentDim}; color: ${a.text}; }
  button.action.alarm.on { border-color: ${a.alarm}; background: #4b1d1d; }

  .session {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 8px 12px;
    align-items: center;
  }
  .session input[type="text"], .session input[type="number"] {
    background: ${a.bg};
    color: ${a.text};
    border: 1px solid ${a.panelBorder};
    border-radius: 6px;
    padding: 6px 8px;
    width: 100%;
    box-sizing: border-box;
    font-size: 13px;
  }
  .session input:focus { outline: none; border-color: ${a.accent}; }
  .session-toggle {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .rec-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: ${a.textDim};
  }
  .rec-dot.live { background: ${a.alarm}; box-shadow: 0 0 8px ${a.alarm}; }

  .chart-host {
    width: 100%;
    min-height: 240px;
    background: ${a.panel};
    border: 1px solid ${a.panelBorder};
    border-radius: 10px;
    overflow: hidden;
  }
  .chart-host canvas { display: block; width: 100%; height: 240px; }

  .alarm-banner {
    background: #4b1d1d;
    border: 1px solid ${a.alarm};
    color: ${a.text};
    padding: 8px 12px;
    border-radius: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
  }
  .alarm-banner.dim {
    background: ${a.panel};
    border-color: ${a.panelBorder};
    color: ${a.textDim};
  }
  .alarm-dismiss {
    background: transparent;
    color: ${a.text};
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 6px;
    width: 26px;
    height: 26px;
    cursor: pointer;
    font-size: 13px;
    line-height: 1;
    flex: 0 0 auto;
    transition: background 0.15s;
  }
  .alarm-dismiss:hover { background: rgba(255,255,255,0.1); }
  .small { font-size: 11px; color: ${a.textDim}; }
  .env-chips { margin-top: 8px; }

  @media (max-width: 600px) {
    .row { grid-template-columns: 1fr; }
  }

  /* Tab strip */
  .tab-strip {
    display: flex;
    gap: 4px;
    background: ${a.panel};
    border-radius: 10px;
    padding: 4px;
    border: 1px solid ${a.panelBorder};
  }
  .tab {
    flex: 1;
    background: transparent;
    color: ${a.textDim};
    border: none;
    border-radius: 7px;
    padding: 8px 12px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 500;
    transition: background 0.15s, color 0.15s;
  }
  .tab:hover { color: ${a.text}; }
  .tab.active {
    background: ${a.bg};
    color: ${a.accent};
    border: 1px solid ${a.panelBorder};
  }

  /* Setup view */
  .setup-grid {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 10px 16px;
    align-items: center;
  }
  .setup-key { color: ${a.textDim}; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
  .setup-val { color: ${a.text}; font-size: 14px; }
  .setup-val.bad { color: ${a.alarm}; }
  .setup-link {
    color: ${a.accent};
    text-decoration: none;
  }
  .setup-link:hover { text-decoration: underline; }
  .auth-actions {
    margin-top: 12px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .auth-flow {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }
  .stepper-input.wide { width: 240px; text-align: left; }
  .auth-error   { color: ${a.alarm};  margin-top: 6px; }
  .auth-success { color: ${a.steady}; margin-top: 6px; }
  .action[disabled] { opacity: 0.6; cursor: not-allowed; }
  .resolved-badge {
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 999px;
    border: 1px solid;
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .resolved-badge.ok  { color: ${a.steady}; border-color: ${a.steady}; background: rgba(34, 197, 94, 0.08); }
  .resolved-badge.bad { color: ${a.alarm};  border-color: ${a.alarm};  background: rgba(248, 113, 113, 0.08); }
  /* Setup uses 3-col grid for sensor rows (label / input / badge) */
  [data-slot="setup"] .sensor-grid {
    grid-template-columns: auto 1fr auto;
  }
  .picker-grid {
    display: grid;
    grid-template-columns: 110px 1fr auto;
    gap: 10px 14px;
    align-items: center;
  }
  .picker-grid label {
    color: ${a.textDim};
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .picker-grid ha-entity-picker {
    display: block;
    width: 100%;
  }
  .cand-host {
    grid-column: 2 / -1;
    margin-top: -2px;
  }
  .cand-row {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .cand-chip {
    background: ${a.bg};
    color: ${a.textDim};
    border: 1px solid ${a.panelBorder};
    border-radius: 999px;
    padding: 3px 10px;
    cursor: pointer;
    font-size: 11px;
    font-family: monospace;
    transition: border-color 0.15s, color 0.15s;
  }
  .cand-chip:hover    { border-color: ${a.accent}; color: ${a.text}; }
  .cand-chip.selected { border-color: ${a.accent}; color: ${a.accent}; background: ${a.accentDim}; }
  code {
    background: ${a.bg};
    border: 1px solid ${a.panelBorder};
    border-radius: 4px;
    padding: 1px 4px;
    font-size: 11px;
  }
`;var j="apexcharts-card",R=class{constructor(e){this._host=e,this._mode=null,this._apexEl=null,this._canvas=null,this._series={},this._historyLoaded=!1,this._lastConfig=null}async update(e,t){let r=t.join("|");if(r!==this._lastConfig&&(this._lastConfig=r,this._historyLoaded=!1,this._series={},this._host.innerHTML="",this._mode=customElements.get(j)?"apex":"canvas",this._mode==="apex"?this._mountApex(t):this._mountCanvas()),this._mode==="apex"){this._apexEl.hass=e;return}this._historyLoaded||(this._historyLoaded=!0,await this._loadHistory(e,t)),this._appendLive(e,t),this._draw(t)}_mountApex(e){let t=e.map((o,n)=>({entity:o,name:this._labelFor(o),yaxis_id:"temp",color:[a.chartChamber,a.chartProbe1,a.chartProbe2][n]||"#fff",type:n===0?"area":"line",opacity:n===0?.25:1,stroke_width:2})),r=document.createElement(j);r.setConfig({header:{show:!1},graph_span:`${S}h`,update_interval:`${B/1e3}s`,yaxis:[{id:"temp",decimals:0,apex_config:{title:{text:"\xB0F"},forceNiceScale:!0}}],series:t}),this._apexEl=r,this._host.appendChild(r)}_mountCanvas(){this._canvas=document.createElement("canvas"),this._host.appendChild(this._canvas)}async _loadHistory(e,t){let n=`history/period/${new Date(Date.now()-S*3600*1e3).toISOString()}?filter_entity_id=${t.join(",")}&minimal_response`;try{let s=await e.callApi("GET",n);for(let c=0;c<t.length;c++){let d=t[c],m=(s?.[c]??[]).map(l=>[Date.parse(l.last_changed),parseFloat(l.state)]).filter(([l,p])=>Number.isFinite(l)&&Number.isFinite(p));this._series[d]=m}}catch(s){console.warn("[ha-prime-polaris-card] history fetch failed:",s)}}_appendLive(e,t){let r=Date.now(),o=r-S*3600*1e3;for(let n of t){let s=this._series[n]??(this._series[n]=[]),c=parseFloat(e.states[n]?.state);if(Number.isFinite(c)){let d=s.length?s[s.length-1][0]:0;r-d>=5e3&&s.push([r,c])}for(;s.length&&s[0][0]<o;)s.shift()}}_draw(e){let t=this._canvas;if(!t)return;let r=window.devicePixelRatio||1,o=t.clientWidth||600,n=240;t.width=o*r,t.height=n*r;let s=t.getContext("2d");s.scale(r,r),s.clearRect(0,0,o,n);let c=e.flatMap(h=>this._series[h]??[]);if(c.length<2){s.fillStyle=a.textDim,s.font="12px system-ui",s.fillText("collecting data\u2026",16,24);return}let d=c.map(h=>h[0]),m=c.map(h=>h[1]),l=Math.min(...d),p=Math.max(...d),u=Math.min(...m)-5,g=Math.max(...m)+5,v={l:36,r:12,t:12,b:22},x=h=>v.l+(h-l)/Math.max(1,p-l)*(o-v.l-v.r),w=h=>v.t+(1-(h-u)/Math.max(1,g-u))*(n-v.t-v.b);s.strokeStyle=a.panelBorder,s.fillStyle=a.textDim,s.font="11px system-ui",s.lineWidth=1;let I=4;for(let h=0;h<=I;h++){let y=u+h/I*(g-u),b=w(y);s.beginPath(),s.moveTo(v.l,b),s.lineTo(o-v.r,b),s.stroke(),s.fillText(y.toFixed(0),6,b+4)}let L=[a.chartChamber,a.chartProbe1,a.chartProbe2];e.forEach((h,y)=>{let b=this._series[h]??[];if(!(b.length<2)){if(s.strokeStyle=L[y]||"#fff",s.lineWidth=y===0?1.5:2,y===0){s.fillStyle=L[0]+"40",s.beginPath(),s.moveTo(x(b[0][0]),w(u));for(let[A,M]of b)s.lineTo(x(A),w(M));s.lineTo(x(b[b.length-1][0]),w(u)),s.closePath(),s.fill()}s.beginPath(),s.moveTo(x(b[0][0]),w(b[0][1]));for(let[A,M]of b)s.lineTo(x(A),w(M));s.stroke()}})}_labelFor(e){return e.includes("chamber")?"Chamber":e.includes("probe_1")?"Probe 1":e.includes("probe_2")?"Probe 2":e}};var E=-135,G=135,ue=G-E;function Y(i){let e=i.size??220,t=e/2,r=e/2,o=e/2-18,n=i.min,s=i.max,c=i.current??n,d=i.target??n,m=U(c,n,s),l=U(d,n,s),p=i.fillColor??me(c,d),u=V(t,r,o,E,G),g=V(t,r,o,E,m),v=T(t,r,o-10,l),x=T(t,r,o+10,l);return`
    <svg
      viewBox="0 0 ${e} ${e}"
      class="arc-gauge"
      data-gauge="true"
      data-min="${n}"
      data-max="${s}"
      data-cx="${t}"
      data-cy="${r}"
      data-r="${o}">

      <!-- track -->
      <path d="${u}"
        stroke="${a.panelBorder}"
        stroke-width="12"
        stroke-linecap="round"
        fill="none" />

      <!-- filled arc up to current -->
      <path d="${g}"
        stroke="${p}"
        stroke-width="12"
        stroke-linecap="round"
        fill="none" />

      <!-- setpoint marker tick -->
      <line
        x1="${v.x}" y1="${v.y}"
        x2="${x.x}" y2="${x.y}"
        stroke="${a.accent}"
        stroke-width="3"
        stroke-linecap="round" />

      <!-- center readout: big chamber temp, small target -->
      <text x="${t}" y="${r-4}"
        text-anchor="middle"
        font-size="44"
        font-weight="600"
        fill="${a.text}"
        style="font-family: inherit;">
        ${i.current!=null?i.current.toFixed(0):"\u2014"}<tspan font-size="22" fill="${a.textDim}">\xB0F</tspan>
      </text>
      <text x="${t}" y="${r+24}"
        text-anchor="middle"
        font-size="13"
        fill="${a.textDim}"
        style="font-family: inherit;">
        target ${i.target??"\u2014"}\xB0F
      </text>
    </svg>
  `}function U(i,e,t){let o=(Math.max(e,Math.min(t,i))-e)/(t-e);return E+o*ue}function T(i,e,t,r){let o=(r-90)*Math.PI/180;return{x:i+t*Math.cos(o),y:e+t*Math.sin(o)}}function V(i,e,t,r,o){let n=T(i,e,t,r),s=T(i,e,t,o),c=Math.abs(o-r)>180?1:0;return`M ${n.x} ${n.y} A ${t} ${t} 0 ${c} 1 ${s.x} ${s.y}`}function me(i,e){if(i==null||e==null)return a.accent;let t=i-e;return t>O?a.hot:t<-O?a.cool:a.steady}var X=[{id:"brisket",name:"Brisket Low & Slow",description:"225\xB0F \xB7 P1\u2192203\xB0F",apply:{setpoint:225,smoke_mode:!1,probe_1_target:203,protein:"brisket"}},{id:"pork_shoulder",name:"Pork Shoulder",description:"250\xB0F \xB7 P1\u2192203\xB0F",apply:{setpoint:250,smoke_mode:!1,probe_1_target:203,protein:"pork shoulder"}},{id:"chicken",name:"Chicken",description:"375\xB0F \xB7 P1\u2192165\xB0F",apply:{setpoint:375,smoke_mode:!1,probe_1_target:165,protein:"chicken"}},{id:"burgers",name:"Burgers",description:"400\xB0F \xB7 P1\u2192160\xB0F",apply:{setpoint:400,smoke_mode:!1,probe_1_target:160,protein:"burgers"}},{id:"sear",name:"Sear",description:"500\xB0F",apply:{setpoint:500,smoke_mode:!1}},{id:"smoke_brisket",name:"Brisket Smoke",description:"Smoke 5 \xB7 P1\u2192203\xB0F \xB7 chamber \xB115\xB0F",apply:{smoke_mode:!0,smoke_level:5,probe_1_target:203,protein:"brisket"}},{id:"smoke_ribs",name:"Ribs Smoke",description:"Smoke 4 \xB7 P1\u2192195\xB0F \xB7 chamber \xB115\xB0F",apply:{smoke_mode:!0,smoke_level:4,probe_1_target:195,protein:"ribs"}},{id:"smoke_only",name:"Smoke Only",description:"Smoke 8 \xB7 chamber \xB115\xB0F",apply:{smoke_mode:!0,smoke_level:8}}];function C(i){if(!Array.isArray(i)||i.length===0)return X;let e=new Map(X.map(t=>[t.id,t]));for(let t of i)!t||!t.id||e.set(t.id,{id:t.id,name:t.name||t.id,description:t.description||"",apply:t.apply||{}});return Array.from(e.values())}function _(i){return String(i??"").replace(/[&<>"']/g,e=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[e])}function K(i){if(!i)return"";let{chamber:e,setpoint:t,chamberDelta:r}=i,o=i.chamber_override?.resolved?.value,n=i.chamber_override?.raw,s=o??e,c=s!=null&&t!=null?s-t:null,d=c!=null?`\u0394 ${c>0?"+":""}${c.toFixed(0)}\xB0F`:"",m=o!=null?`<div class="small">controller ${e!=null?e.toFixed(0)+"\xB0F":"\u2014"} \xB7 using override</div>`:n?'<div class="small" style="color:var(--error-color,#f87171)">override unresolved</div>':"",l=t??225;return`
    <div class="panel tall arc-panel">
      <div class="panel-label">Chamber</div>
      ${Y({min:180,max:500,current:s,target:t})}
      <div class="delta">${d}</div>
      ${m}
      <div class="stepper-row chamber-setpoint">
        <span class="stepper-label">Setpoint</span>
        <button class="action stepper-btn" data-action="temp-down">\u2212</button>
        <input
          type="number"
          inputmode="numeric"
          min="180"
          max="500"
          step="1"
          class="stepper-input"
          data-input="setpoint"
          value="${l}">
        <span class="stepper-unit">\xB0F</span>
        <button class="action stepper-btn" data-action="temp-up">+</button>
      </div>
    </div>
  `}function J(i){if(!i)return"";let e=[];return i.runningStatus&&e.push({cls:"active",txt:Q(i.runningStatus)}),e.push({cls:i.activeMode==="smoke"?"smoke":"active",txt:`Mode: ${Q(i.activeMode)}`}),i.smokeOn&&i.smokeLevel!=null&&e.push({cls:"smoke",txt:`Smoke ${i.smokeLevel.toFixed(0)}`}),i.alarmOn&&e.push({cls:"alarm",txt:"Alarm Armed"}),i.winterOn&&e.push({cls:"active",txt:"Winter"}),i.pushOn&&e.push({cls:"active",txt:"Push On"}),i.ambient&&e.push(i.ambientResolved.value!=null?{cls:"active",txt:`Ambient ${i.ambientResolved.value.toFixed(0)}\xB0F`}:{cls:"alarm",txt:"Ambient Unresolved"}),i.wind&&e.push(i.windResolved.value!=null?{cls:"active",txt:`Wind ${i.windResolved.value.toFixed(1)}`}:{cls:"alarm",txt:"Wind Unresolved"}),`
    <div class="chip-row">
      ${e.map(t=>`<span class="chip ${t.cls}">${_(t.txt)}</span>`).join("")}
    </div>
  `}function Q(i){return i?String(i).split(/(\s+)/).map(e=>e.length===0||/\s+/.test(e)?e:e[0].toUpperCase()+e.slice(1).toLowerCase()).join(""):""}function ee(i){if(!i)return"";let e=i.cookSession,t=e?i.protein?`${_(i.protein)}${i.weight_lb?" \xB7 "+_(i.weight_lb)+" lb":""}`:"recording":"no active cook",r=i.notes?_(i.notes):e?"":"flip the switch when you start a real cook",o=[];i.ambientResolved.value!=null&&o.push(`<span class="chip active">Ambient ${i.ambientResolved.value.toFixed(0)}\xB0F</span>`),i.windResolved.value!=null&&o.push(`<span class="chip active">Wind ${i.windResolved.value.toFixed(1)}</span>`);let n=o.length?`<div class="chip-row env-chips">${o.join("")}</div>`:"";return`
    <div class="panel tall">
      <div class="panel-label">Cook session</div>
      <div class="session-toggle">
        <span class="rec-dot ${e?"live":""}"></span>
        <button class="action ${e?"on":""}" data-action="toggle-session">
          ${e?"Stop session":"Start session"}
        </button>
      </div>
      <div class="big-temp" style="font-size:22px; margin-top:8px;">${t}</div>
      <div class="small">${r}</div>
      ${n}
    </div>
  `}function Z(i,e){let t=e.override_resolved?.value,r=e.override_raw,o=t??e.temp;if(o==null)return`
      <div class="panel">
        <div class="probe">
          <div class="probe-label">Probe ${i}</div>
          <div class="small">not connected</div>
        </div>
      </div>
    `;let n="fitting\u2026",s="fitting";if(e.in_stall)n=`\u{1F6D1} in stall \xB7 \u03C3 ${e.stdev?.toFixed(2)??"\u2014"}\xB0F`,s="stall";else if(e.minutes!=null){let d=Math.max(0,e.minutes);n=d>=60?`ETA ${(d/60).toFixed(1)} h`:`ETA ${d.toFixed(0)} min`,s=""}let c=t!=null?`<div class="small">OEM ${e.temp!=null?e.temp.toFixed(0)+"\xB0F":"\u2014"} \xB7 using override</div>`:r?'<div class="small" style="color:var(--error-color,#f87171)">override unresolved</div>':"";return`
    <div class="panel">
      <div class="probe">
        <div class="probe-label">Probe ${i}</div>
        <div>
          <div class="probe-temp">${o.toFixed(0)}\xB0F</div>
          <div class="probe-target">\u2192 ${e.target??"\u2014"}\xB0F</div>
          <div class="probe-eta ${s}">${_(n)}</div>
          ${c}
          ${e.source?`<div class="small">prior: ${_(e.source)}</div>`:""}
        </div>
      </div>
    </div>
  `}function te(i){return i?`
    <div class="row">
      ${Z(1,i.probe1)}
      ${Z(2,i.probe2)}
    </div>
  `:""}function ie(i,e){if(!i)return"";let t=C(e?.recipes);return t.length===0?"":`
    <div class="panel">
      <div class="panel-label">Recipes</div>
      <div class="recipe-grid">
        ${t.map(r=>`
          <button class="recipe-tile"
                  data-action="apply-recipe"
                  data-recipe-id="${r.id}"
                  title="${_(r.description||"")}">
            <span class="recipe-name">${_(r.name)}</span>
            <span class="recipe-desc">${_(r.description||"")}</span>
          </button>`).join("")}
      </div>
      <div class="small" style="margin-top:6px;">
        Tap to apply grill temp, smoke, and probe targets in one shot.
        Time stays yours to manage. Smoke mode runs a P-cycle (not PID),
        so chamber temp swings \xB110\u201320\xB0F by design.
      </div>
    </div>
  `}function re(i){if(!i)return"";let e=i.smokeLevel??0;return`
    <div class="panel">
      <div class="panel-label">Controls</div>
      <div class="stepper-row">
        <span class="stepper-label">Smoke level</span>
        <input
          type="range"
          min="0"
          max="9"
          step="1"
          class="slider"
          data-input="smoke_level"
          value="${e}">
        <span class="stepper-unit" data-bind="smoke-level-readout">${e}</span>
      </div>
      <div class="controls">
        <button class="action ${i.smokeOn?"on":""}" data-action="toggle-smoke">Smoke</button>
        <button class="action ${i.winterOn?"on":""}" data-action="toggle-winter">Winter</button>
        <button class="action alarm ${i.alarmOn?"on":""}" data-action="toggle-alarm">Alarm</button>
        <button class="action ${i.pushOn?"on":""}" data-action="toggle-push">Push</button>
        <button class="action" data-action="power-off">Power off</button>
      </div>
    </div>
  `}function se(i){return i?`
    <div class="panel">
      <div class="panel-label">This cook</div>
      <div class="session">
        <label>Protein</label>
        <input type="text" data-input="protein"   value="${_(i.protein)}"   placeholder="brisket / pork / ribs">
        <label>Weight (lb)</label>
        <input type="text" data-input="weight_lb" value="${_(i.weight_lb)}" placeholder="16">
        <label>Notes</label>
        <input type="text" data-input="notes"     value="${_(i.notes)}"     placeholder="oak, low and slow">
      </div>
      <div class="small" style="margin-top:8px;">
        Ambient / wind sensors are configured once in the
        <strong>Setup</strong> tab and persist across cooks.
      </div>
    </div>
  `:""}function oe(i){let e=(t,r)=>`
    <button class="tab ${i===t?"active":""}"
            data-action="set-view-${t}">
      ${r}
    </button>
  `;return`
    <div class="tab-strip">
      ${e("live","Live")}
      ${e("setup","Setup")}
    </div>
  `}function ae(i,e){if(!i)return"";let t=i.lastAlarm;return t?e&&e===t.captured_at?'<div class="alarm-banner dim">no alarms (dismissed)</div>':`
    <div class="alarm-banner">
      <span><strong>${_(t.title)}</strong> \xB7 ${_(t.body)}</span>
      <button class="alarm-dismiss" data-action="dismiss-alarm" title="Dismiss">\u2715</button>
    </div>
  `:'<div class="alarm-banner dim">no alarms</div>'}function f(i){return String(i??"").replace(/[&<>"']/g,e=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"})[e])}var le=/\b(indoor|inside|bedroom|bathroom|kitchen|living|hallway|office|garage|attic|basement|fridge|freezer|oven|refrigerator|dishwasher|washer|dryer|cpu|gpu|battery|server|chip|water_heater|coolant|pool|spa|jacuzzi|hot_tub|aquarium|fishtank|car|vehicle|engine)\b/i,he=/(?<![a-zA-Z])(feels[ _-]?like|apparent[ _-]?(?:temp|temperature)|dew[ _-]?point|heat[ _-]?index|wind[ _-]?chill|windchill)(?![a-zA-Z])/i,_e=/\b(outdoor|outside|exterior|patio|deck|porch|backyard|yard|weather|ambient|station|pws|awn|tempest|davis|ecowitt|netatmo)\b/i,ce=/(ambient[a-z]*network|ambientweather|tempest|weatherflow|openweathermap|dark[- ]?sky|met\.no|met office|accuweather|weather\.gov|nws|pirate weather|aemet|wunderground|weatherapi|netatmo|ecowitt|davis\b|wxinsight|meteo|aprs|ambientcwop|cwop|airnow)/i,be=/\b(mph|m\/s|km\/h|knots?)\b/i,ve=/\bwind\b/i,fe=/(?<![a-zA-Z])gust(?![a-zA-Z])/i;function ge(i,e){if(!i)return[];let t=e?new RegExp(`^[a-z_]+\\.${e.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}_`,"i"):null,r=[];for(let[o,n]of Object.entries(i.states)){if(t&&t.test(o)||le.test(o)||he.test(o))continue;if(o.startsWith("weather.")){let g=parseFloat(n.attributes?.temperature);Number.isFinite(g)&&r.push({eid:o,value:g,unit:"\xB0F"});continue}let s=n.attributes?.device_class,c=n.attributes?.unit_of_measurement||"";if(!(s==="temperature"||/°[FC]|degf|degc/i.test(c)))continue;let m=_e.test(o),l=String(n.attributes?.attribution||""),p=ce.test(l);if(!m&&!p)continue;let u=parseFloat(n.state);Number.isFinite(u)&&r.push({eid:o,value:u,unit:c||"\xB0F"})}return r.sort((o,n)=>{let s=o.eid.startsWith("weather.")?0:1,c=n.eid.startsWith("weather.")?0:1;return s-c||o.eid.localeCompare(n.eid)}).slice(0,6)}function xe(i,e){if(!i)return[];let t=e?new RegExp(`^[a-z_]+\\.${e.replace(/[.*+?^${}()|[\]\\]/g,"\\$&")}_`,"i"):null,r=[];for(let[o,n]of Object.entries(i.states)){if(t&&t.test(o)||le.test(o)||fe.test(o))continue;let s=n.attributes?.unit_of_measurement||"";if(!be.test(s))continue;let c=ve.test(o),d=String(n.attributes?.attribution||""),m=ce.test(d);if(!c&&!m)continue;let l=parseFloat(n.state);Number.isFinite(l)&&r.push({eid:o,value:l,unit:s})}return r.sort((o,n)=>o.eid.localeCompare(n.eid)).slice(0,4)}function we(i,e,t){return i.length?`
    <div class="cand-row">
      ${i.map(r=>`
        <button class="cand-chip ${r.eid===t?"selected":""}"
                data-action="apply-default"
                data-purpose="${e}"
                data-value="${f(r.eid)}"
                title="Click to use this sensor">
          ${f(r.eid)} \xB7 ${r.value.toFixed(1)}${r.unit?" "+f(r.unit):""}
        </button>`).join("")}
    </div>
  `:""}function z(i,e,t,r){let o="";return t&&(o=r&&r.value!=null?`<span class="resolved-badge ok">${r.value.toFixed(1)}\xB0F</span>`:'<span class="resolved-badge bad">unresolved</span>'),`
    <label>${i}</label>
    <ha-entity-picker
      data-input="${e}"
      data-current="${f(t||"")}"
      data-include-domains="sensor,input_number,weather,number"
      data-include-device-classes="temperature"
      allow-custom-entity>
    </ha-entity-picker>
    ${o||"<span></span>"}
  `}function ne(i,e,t,r,o,n){let s="";return t&&(s=r&&r.value!=null?`<span class="resolved-badge ok">${r.value.toFixed(1)}${o}</span>`:'<span class="resolved-badge bad">unresolved</span>'),`
    <label>${i}</label>
    <input type="text" data-input="${e}" value="${f(t)}" placeholder="entity_id (e.g. sensor.outdoor_temp)">
    ${s||"<span></span>"}
    <span></span>
    <div class="cand-host">${we(n,e,t)}</div>
    <span></span>
  `}function pe(i,e,t,r){if(!i||!i.account)return`
      <div class="panel"><div class="small">Loading account info\u2026</div></div>
    `;let o=i.account,n=o.daysToExpiry!=null&&o.daysToExpiry<14?"bad":"",s=r||{stage:"idle",email:o.email||"",error:""},c="";return s.stage==="idle"?c=`
      <button class="action" data-action="auth-start">Re-authenticate</button>
      <button class="action" data-action="reset-cook-inputs"
              title="Clears notes / protein / weight">Reset cook inputs</button>
    `:s.stage==="email"||s.stage==="sending"?c=`
      <div class="auth-flow">
        <input type="email" class="stepper-input wide"
               data-input="auth_email"
               value="${f(s.email)}"
               placeholder="email@example.com"
               autocomplete="email">
        <button class="action ${s.stage==="sending"?"on":""}"
                data-action="auth-request-otp"
                ${s.stage==="sending"?"disabled":""}>
          ${s.stage==="sending"?"Sending\u2026":"Send code"}
        </button>
        <button class="action" data-action="auth-cancel">Cancel</button>
      </div>
      ${s.error?`<div class="small auth-error">${f(s.error)}</div>`:""}
    `:s.stage==="otp"||s.stage==="verifying"?c=`
      <div class="setup-grid" style="margin-bottom:8px;">
        <span class="setup-key">Email</span>
        <span class="setup-val">${f(s.email)}</span>
      </div>
      <div class="auth-flow">
        <input type="text" inputmode="numeric" maxlength="10"
               class="stepper-input"
               data-input="auth_otp"
               value="${f(s.otp||"")}"
               placeholder="6-digit code"
               autocomplete="one-time-code">
        <button class="action ${s.stage==="verifying"?"on":""}"
                data-action="auth-verify-otp"
                ${s.stage==="verifying"?"disabled":""}>
          ${s.stage==="verifying"?"Verifying\u2026":"Sign in"}
        </button>
        <button class="action" data-action="auth-cancel">Cancel</button>
      </div>
      ${s.error?`<div class="small auth-error">${f(s.error)}</div>`:""}
    `:s.stage==="done"&&(c='<div class="small auth-success">\u2713 Re-authenticated successfully.</div>'),`
    <div class="panel">
      <div class="panel-label">Account</div>
      <div class="setup-grid">
        <span class="setup-key">Email</span>
        <span class="setup-val">${f(o.email||"\u2014")}</span>

        <span class="setup-key">Token expires</span>
        <span class="setup-val ${n}">
          ${o.daysToExpiry!=null?`in ${o.daysToExpiry} days`:"\u2014"}
        </span>
      </div>
      <div class="auth-actions">${c}</div>
    </div>

    <div class="panel">
      <div class="panel-label">Push alerts (FCM)</div>
      <div class="setup-grid">
        <span class="setup-key">Enabled</span>
        <span class="setup-val">
          <button class="action ${i.pushOn?"on":""}" data-action="toggle-push">
            ${i.pushOn?"ON":"OFF"}
          </button>
        </span>

        <span class="setup-key">Dedupe window</span>
        <span class="setup-val">
          <input type="number" min="10" max="3600" step="10"
                 class="stepper-input"
                 data-input="push_dedupe"
                 value="${i.pushDedupe??60}">
          <span class="stepper-unit">sec</span>
        </span>
      </div>
      <div class="small" style="margin-top:8px;">
        Pushes for the same alarm category fire every ~25\u201330 s while the
        condition persists; the dedupe window suppresses repeats.
      </div>
    </div>

    <div class="panel">
      <div class="panel-label">Probe / chamber overrides</div>
      <div class="small" style="margin-bottom:10px;">
        OEM grill probes can drift up to 30\xB0F vs reference probes. Point
        the predictor at any HA temperature sensor you trust more \u2014 a
        wireless meat thermometer, instant-read bridge, or quality probe
        from another integration. ETA / stall calculations use the
        override value instead. Leave blank to use OEM.
      </div>
      <div class="picker-grid">
        ${z("Chamber","chamber_override",i.chamber_override.raw,i.chamber_override.resolved)}
        ${z("Probe 1","probe_1_override",i.probe1.override_raw,i.probe1.override_resolved)}
        ${z("Probe 2","probe_2_override",i.probe2.override_raw,i.probe2.override_resolved)}
      </div>
    </div>

    <div class="panel">
      <div class="panel-label">Default sensors</div>
      <div class="small" style="margin-bottom:10px;">
        Point these at any HA temperature / wind sensor. Common picks:
        a <strong>weather.*</strong> entity (HA's default weather integration),
        a <strong>sensor.*</strong> from your weather station / Ambient Weather Network,
        or just a fixed number (e.g. <code>32</code>) for cooks at a known temp.
        Set once \u2014 per-cook overrides on the Live tab take precedence if you ever deviate.
      </div>
      <div class="session sensor-grid">
        ${ne("Ambient sensor","ambient",i.ambient,i.ambientResolved,"\xB0F",ge(t,e?.entity_prefix))}
        ${ne("Wind sensor","wind",i.wind,i.windResolved,"",xe(t,e?.entity_prefix))}
      </div>
      <div class="small" style="margin-top:8px;">
        \u{1F4A1} Suggestions match weather-integration sources:
        <strong>weather.*</strong> entities, sensors with outdoor hints in their
        entity_id, OR sensors whose <em>attribution</em> attribute names a known
        weather provider (AWN, Tempest, OpenWeatherMap, NWS, AccuWeather, etc).
        If yours doesn't appear, just type the entity_id manually.
      </div>
    </div>
  `}var N=class extends HTMLElement{constructor(){super(),this.attachShadow({mode:"open"}),this._hass=null,this._config=null,this._state=null,this._chart=null,this._view="live",this._dismissedAlarmId=null,this._otpFlow={stage:"idle",email:"",otp:"",error:""},this._renderQueued=!1}setConfig(e){this._config={entity_prefix:e?.entity_prefix??P,title:e?.title??null,ambient_entity:e?.ambient_entity??null,...e},this._lastSig=null}set hass(e){this._hass=e,this._config&&(this._state=W(e,this._config.entity_prefix),this._scheduleRender())}getCardSize(){return 8}static getConfigElement(){return null}static getStubConfig(){return{entity_prefix:P}}_scheduleRender(){this._renderQueued||(this._renderQueued=!0,requestAnimationFrame(()=>{this._renderQueued=!1,this._render()}))}_render(){let e=this._state;(!this.shadowRoot.firstElementChild||this.shadowRoot.firstElementChild.dataset.view!==this._view)&&(this._stampShell(),this._wireEvents()),this._fill("tabs",oe(this._view)),this._view==="live"?this._renderLive(e):this._renderSetup(e)}_stampShell(){let e=`
      <div data-slot="alarm"></div>
      <div data-slot="chips"></div>
      <div class="row">
        <div data-slot="chamber"></div>
        <div data-slot="cookHeader"></div>
      </div>
      <div data-slot="probes"></div>
      <div class="chart-host" data-slot="chart"></div>
      <div data-slot="recipes"></div>
      <div data-slot="controls"></div>
      <div data-slot="session"></div>
    `,t=`
      <div data-slot="setup"></div>
    `;this.shadowRoot.innerHTML=`
      <style>${q}</style>
      <div class="card" data-view="${this._view}">
        <div data-slot="tabs"></div>
        ${this._view==="live"?e:t}
      </div>
    `,this._view!=="live"&&(this._chart=null)}_renderLive(e){if(this._fill("alarm",ae(e,this._dismissedAlarmId)),this._fill("chips",J(e)),this._fill("cookHeader",ee(e)),this._fill("probes",te(e)),this._fillPreserveFocus("chamber",K(e)),this._fill("recipes",ie(e,this._config)),this._fillPreserveFocus("controls",re(e)),this._fillPreserveFocus("session",se(e)),this._hass&&e){if(!this._chart){let r=this.shadowRoot.querySelector('[data-slot="chart"]');this._chart=new R(r)}let t=[e.entityIds.chamber_temp,e.entityIds.probe_1_temp,e.entityIds.probe_2_temp];this._chart.update(this._hass,t)}}_renderSetup(e){this._fillPreserveFocus("setup",pe(e,this._config,this._hass,this._otpFlow)),this._hydrateEntityPickers()}_hydrateEntityPickers(){let e=this.shadowRoot.querySelector('[data-slot="setup"]');if(!e||!this._hass)return;let t=e.querySelectorAll("ha-entity-picker");for(let r of t){r.hass=this._hass;let o=r.dataset.current||"";r.value!==o&&(r.value=o);let n=r.dataset.includeDomains;n&&(r.includeDomains=n.split(","));let s=r.dataset.includeDeviceClasses;s&&(r.includeDeviceClasses=s.split(",")),r.__hpListenerAttached||(r.__hpListenerAttached=!0,r.addEventListener("value-changed",c=>{let d=r.dataset.input,m=c.detail?.value??"",p={chamber_override:"chamber_override",probe_1_override:"probe_1_override",probe_2_override:"probe_2_override"}[d];p&&this._hass&&this._state&&k(this._hass,this._state).setText(p,m)}))}}_fill(e,t){let r=this.shadowRoot.querySelector(`[data-slot="${e}"]`);r&&(r.innerHTML=t)}_fillPreserveFocus(e,t){let r=this.shadowRoot.querySelector(`[data-slot="${e}"]`);if(!r)return;let o=this.shadowRoot.activeElement;if(!(o&&o.dataset?.input&&r.contains(o))){r.innerHTML=t;return}let s=o.dataset.input,c=o.value,d=o.selectionStart,m=o.selectionEnd;r.innerHTML=t;let l=r.querySelector(`[data-input="${s}"]`);if(l){l.value=c,l.focus();try{l.setSelectionRange(d,m)}catch{}}}_wireEvents(){this.shadowRoot.addEventListener("click",e=>{let t=e.target.closest("[data-action]");if(t){if(t.dataset.action==="apply-default"){let r=t.dataset.purpose,o=t.dataset.value;if(!this._hass||!this._state||!r)return;let s={ambient:"ambient_override",wind:"wind_override",chamber_override:"chamber_override",probe_1_override:"probe_1_override",probe_2_override:"probe_2_override"}[r];s&&k(this._hass,this._state).setText(s,o);return}if(t.dataset.action==="apply-recipe"){this._applyRecipe(t.dataset.recipeId);return}this._dispatchAction(t.dataset.action)}}),this.shadowRoot.addEventListener("change",e=>{let t=e.target.closest("[data-input]");if(!t)return;let r=k(this._hass,this._state),o=t.dataset.input;if(o==="setpoint"){let s=parseInt(t.value,10);Number.isFinite(s)&&r.setSetpoint(Math.max(180,Math.min(500,s)));return}if(o==="smoke_level"){let s=parseInt(t.value,10);Number.isFinite(s)&&r.setSmokeLevel(Math.max(0,Math.min(9,s)));return}if(o==="push_dedupe"){let s=parseInt(t.value,10);Number.isFinite(s)&&this._hass.callService("number","set_value",{entity_id:this._state.entityIds.push_dedupe,value:Math.max(10,Math.min(3600,s))});return}if(o==="auth_email"){this._otpFlow.email=t.value;return}if(o==="auth_otp"){this._otpFlow.otp=t.value;return}let n={notes:"notes",protein:"protein",weight_lb:"weight_lb",ambient:"ambient_override",wind:"wind_override",chamber_override:"chamber_override",probe_1_override:"probe_1_override",probe_2_override:"probe_2_override"};n[o]&&r.setText(n[o],t.value)}),this.shadowRoot.addEventListener("input",e=>{let t=e.target.closest("[data-input]");if(!t)return;let r=t.dataset.input;if(r==="smoke_level"){let o=this.shadowRoot.querySelector('[data-bind="smoke-level-readout"]');o&&(o.textContent=t.value)}r==="auth_email"&&(this._otpFlow.email=t.value),r==="auth_otp"&&(this._otpFlow.otp=t.value)})}_authStart(){this._otpFlow={stage:"email",email:this._state?.account?.email||"",otp:"",error:""},this._scheduleRender()}_authCancel(){this._otpFlow={stage:"idle",email:"",otp:"",error:""},this._scheduleRender()}async _authRequestOtp(){if(!this._hass)return;let e=(this._otpFlow.email||"").trim();if(!e){this._otpFlow.error="Email required",this._scheduleRender();return}this._otpFlow.stage="sending",this._otpFlow.error="",this._scheduleRender();try{await this._hass.callService("prime_polaris","request_otp",{email:e}),this._otpFlow.stage="otp"}catch(t){this._otpFlow.stage="email",this._otpFlow.error=t?.message||String(t)}this._scheduleRender()}async _authVerifyOtp(){if(!this._hass)return;let e=(this._otpFlow.email||"").trim(),t=(this._otpFlow.otp||"").trim();if(!t){this._otpFlow.error="Enter the code",this._scheduleRender();return}this._otpFlow.stage="verifying",this._otpFlow.error="",this._scheduleRender();try{await this._hass.callService("prime_polaris","verify_otp",{email:e,otp:t}),this._otpFlow.stage="done",this._scheduleRender(),setTimeout(()=>{this._otpFlow.stage==="done"&&(this._otpFlow={stage:"idle",email:"",otp:"",error:""},this._scheduleRender())},2500)}catch(r){this._otpFlow.stage="otp",this._otpFlow.error=r?.message||String(r),this._scheduleRender()}}async _resetCookInputs(){if(this._hass)try{await this._hass.callService("prime_polaris","clear_cook_inputs",{})}catch(e){console.warn("clear_cook_inputs failed:",e)}}async _applyRecipe(e){if(!this._hass||!this._state||!e)return;let r=C(this._config?.recipes).find(s=>s.id===e);if(!r||!r.apply)return;let o=k(this._hass,this._state),n=r.apply;try{n.setpoint!=null&&await o.setSetpoint(Math.max(180,Math.min(500,n.setpoint))),n.smoke_level!=null&&await o.setSmokeLevel(Math.max(0,Math.min(9,n.smoke_level))),n.smoke_mode!=null&&n.smoke_mode!==this._state.smokeOn&&await o.toggle("smoke_mode"),n.probe_1_target!=null&&await o.setProbeTarget(1,Math.max(100,n.probe_1_target)),n.probe_2_target!=null&&await o.setProbeTarget(2,Math.max(100,n.probe_2_target)),n.protein!=null&&await o.setText("protein",n.protein)}catch(s){console.warn(`apply-recipe (${e}) failed mid-sequence:`,s)}}_dispatchAction(e){if(!this._hass||!this._state)return;let t=k(this._hass,this._state),r=this._state.setpoint??225;switch(e){case"toggle-session":t.toggle("cook_session");break;case"toggle-smoke":t.toggle("smoke_mode");break;case"toggle-winter":t.toggle("winter_mode");break;case"toggle-alarm":t.toggle("alarm");break;case"toggle-push":t.toggle("push_alerts");break;case"temp-up":t.setSetpoint(Math.min(500,r+1));break;case"temp-down":t.setSetpoint(Math.max(180,r-1));break;case"power-off":t.powerOff();break;case"set-view-live":this._view="live",this._scheduleRender();break;case"set-view-setup":this._view="setup",this._scheduleRender();break;case"dismiss-alarm":this._state?.lastAlarm&&(this._dismissedAlarmId=this._state.lastAlarm.captured_at,this._scheduleRender());break;case"auth-start":this._authStart();break;case"auth-cancel":this._authCancel();break;case"auth-request-otp":this._authRequestOtp();break;case"auth-verify-otp":this._authVerifyOtp();break;case"reset-cook-inputs":this._resetCookInputs();break}}};customElements.get($)||customElements.define($,N);window.customCards=window.customCards||[];window.customCards.some(i=>i.type===$)||window.customCards.push({type:$,name:"Prime Polaris Grill",description:"Live cook dashboard for the Prime Polaris pellet grill integration.",preview:!0});console.info(`%c ${$} %c v${H} `,"color:#fb923c;background:#0d1117;padding:2px 6px;border-radius:3px 0 0 3px;font-weight:600","color:#0d1117;background:#fb923c;padding:2px 6px;border-radius:0 3px 3px 0");
