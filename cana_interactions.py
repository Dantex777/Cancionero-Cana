"""Interacciones locales de navegador para Cancionero Caná (rama de prueba).

El código JavaScript es fijo, no recibe texto ni credenciales de Notion.
Requiere Streamlit con st.html(..., unsafe_allow_javascript=True).
"""
AUTO_SCROLL_HTML = r"""
<style>
.cana-scroll-toolbar{display:flex;align-items:center;gap:.35rem;background:#222330;
border:1px solid #45435d;border-radius:9px;padding:.35rem .5rem;margin:.3rem 0 .75rem;color:#eee;}
.cana-scroll-toolbar label{font-weight:700;font-size:.84rem;white-space:nowrap;}
.cana-scroll-toolbar select{flex:1;min-width:0;max-width:180px;padding:.34rem;
color:#f4f2f8;background:#191a23;border:1px solid #55516c;border-radius:6px;}
.cana-scroll-toolbar button{color:#fff;background:#363548;border:1px solid #706b88;
border-radius:6px;min-width:34px;min-height:34px;cursor:pointer;}
.cana-scroll-toolbar button:disabled{opacity:.45;cursor:default;}
.cana-song.cana-auto-active{max-height:68dvh;overflow-y:auto;
overscroll-behavior:contain;-webkit-overflow-scrolling:touch;scrollbar-width:thin;}
@media(max-width:640px){
.cana-scroll-toolbar{gap:.25rem;padding:.3rem;}
.cana-scroll-toolbar label{font-size:.78rem;}
.cana-scroll-toolbar select{font-size:.78rem;}
.cana-song.cana-auto-active{max-height:66dvh;}
}
</style>
<div class="cana-scroll-toolbar" id="cana-autoscroll-toolbar" role="group" aria-label="Desfile automático">
<label for="cana-scroll-speed">Auto Scroll</label>
<select id="cana-scroll-speed" aria-label="Velocidad del Auto Scroll">
<option value="0">Apagado</option><option value="1">1 · Muy lento</option>
<option value="2">2</option><option value="3">3</option><option value="4">4</option>
<option value="5">5</option><option value="6">6</option><option value="7">7 · Rápido</option>
</select>
<button id="cana-scroll-play" aria-label="Pausar o reanudar" title="Pausar o reanudar" disabled>▶</button>
<button id="cana-scroll-reset" aria-label="Volver al inicio" title="Volver al inicio">↺</button>
</div>
<script>
(()=>{
  if(window.__canaScrollCleanup)window.__canaScrollCleanup();
  const toolbar=document.getElementById('cana-autoscroll-toolbar');
  if(!toolbar)return;
  const selector=toolbar.querySelector('#cana-scroll-speed');
  const play=toolbar.querySelector('#cana-scroll-play');
  const reset=toolbar.querySelector('#cana-scroll-reset');
  // Distancia perceptible y MUY lenta: 3–21 píxeles por segundo.
  const pixelsPerSecond=[0,3,5,7,10,13,17,21];
  let speed=0,running=false,raf=null,last=null,desiredTop=0;
  const subs=[];
  const viewer=()=>document.querySelector('.cana-song');
  const listen=(node,event,fn,opts)=>{
    node.addEventListener(event,fn,opts);
    subs.push(()=>node.removeEventListener(event,fn,opts));
  };
  function sync(){
    play.disabled=speed===0;
    play.textContent=running?'Ⅱ':'▶';
    play.setAttribute('aria-label',running?'Pausar Auto Scroll':'Continuar Auto Scroll');
  }
  function pause(){
    running=false;last=null;
    if(raf!==null)cancelAnimationFrame(raf);
    raf=null;sync();
  }
  function animate(ts){
    if(!running)return;
    const node=viewer();
    if(!node||!node.isConnected){pause();return;}
    const max=Math.max(0,node.scrollHeight-node.clientHeight);
    if(last!==null){
      const seconds=Math.min(Math.max((ts-last)/1000,0),0.10);
      // Conservamos fracciones de píxel en el acumulador, porque iOS
      // puede redondear scrollTop y perder incrementos pequeños.
      desiredTop=Math.min(max,desiredTop+pixelsPerSecond[speed]*seconds);
      const target=Math.round(desiredTop);
      if(target!==Math.round(node.scrollTop))node.scrollTop=target;
      if(desiredTop>=max-0.5){pause();return;}
    }
    last=ts;
    raf=requestAnimationFrame(animate);
  }
  function start(){
    const node=viewer();
    if(!speed||!node)return;
    node.classList.add('cana-auto-active');
    if(node.scrollHeight<=node.clientHeight+1){pause();return;}
    if(raf!==null)cancelAnimationFrame(raf);
    desiredTop=node.scrollTop;last=null;running=true;sync();
    raf=requestAnimationFrame(animate);
  }
  function changeSpeed(){
    speed=Number(selector.value)||0;
    const node=viewer();
    if(!speed){
      pause();
      if(node)node.classList.remove('cana-auto-active');
    }else start();
  }
  function restart(){
    pause();speed=0;selector.value='0';
    const node=viewer();
    if(node){node.scrollTop=0;node.classList.remove('cana-auto-active');}
    sync();
  }
  function touchSong(evt){
    const node=viewer();
    if(node&&node.contains(evt.target))pause();
  }
  listen(selector,'change',changeSpeed);
  listen(play,'click',()=>running?pause():start());
  listen(reset,'click',restart);
  listen(document,'pointerdown',touchSong,{passive:true});
  listen(document,'touchstart',touchSong,{passive:true});
  listen(document,'wheel',touchSong,{passive:true});
  listen(document,'visibilitychange',()=>{if(document.hidden)pause();});
  listen(document,'keydown',evt=>{
    if(['ArrowDown','ArrowUp','PageDown','PageUp',' '].includes(evt.key))pause();
  });
  sync();
  window.__canaScrollCleanup=()=>{
    pause();subs.forEach(unsubscribe=>unsubscribe());
    const node=viewer();
    if(node)node.classList.remove('cana-auto-active');
  };
})();
</script>
"""

def sidebar_helper_html(command: int) -> str:
    """Cierre móvil de mejor esfuerzo usando el botón nativo de Streamlit.

    Nunca oculta la barra únicamente por CSS; conserva el estado de React.
    """
    markup = r"""
<style>
.cana-mobile-close{position:fixed;top:12px;right:12px;z-index:999999;
color:#fff;background:#353349;border:1px solid #a99bd3;border-radius:9px;
padding:7px 10px;font:600 12px system-ui,sans-serif;cursor:pointer;
box-shadow:0 2px 10px #0008;display:none;}
@media(max-width:1024px){.cana-mobile-close[data-open="true"]{display:block;}}
</style>
<div id="cana-sidebar-command" data-counter="__COMMAND__" hidden></div>
<script>
(()=>{
  if(window.__canaMenuCleanup)window.__canaMenuCleanup();
  const source=document.getElementById('cana-sidebar-command');
  if(!source)return;
  const command=Number(source.getAttribute('data-counter')||0);
  const sidebar=()=>document.querySelector('[data-testid="stSidebar"]');
  const isExpanded=()=>{
    const sb=sidebar();if(!sb)return false;
    // Streamlit expone su estado real en aria-expanded (estable en Sidebar.tsx).
    const attr=sb.getAttribute('aria-expanded');
    if(attr==='true')return true;
    if(attr==='false')return false;
    return sb.getBoundingClientRect().width>90;
  };
  function close(){
    const sb=sidebar();
    if(!sb||!isExpanded())return true;
    const native=sb.querySelector('[data-testid="stSidebarCollapseButton"] button');
    if(!native)return false;
    native.click();return true;
  }
  let button=document.getElementById('cana-floating-close');
  if(!button){
    button=document.createElement('button');
    button.id='cana-floating-close';
    button.className='cana-mobile-close';
    button.type='button';
    button.textContent='✕ Cerrar menú';
    document.body.appendChild(button);
  }
  const click=()=>close();
  const refresh=()=>{button.dataset.open=isExpanded()?'true':'false';};
  button.addEventListener('click',click);
  const sb=sidebar();
  let observer=null,timer=null;
  if(sb){
    observer=new MutationObserver(refresh);
    observer.observe(sb,{attributes:true,attributeFilter:['aria-expanded','class','style']});
  }
  window.addEventListener('resize',refresh);
  refresh();
  if(command>0&&window.__canaLastCloseCommand!==command){
    window.__canaLastCloseCommand=command;
    let attempts=0;
    const tryClose=()=>{
      attempts++;
      if(!close()&&attempts<8)timer=setTimeout(tryClose,150);
      refresh();
    };
    timer=setTimeout(tryClose,140);
  }
  window.__canaMenuCleanup=()=>{
    if(timer)clearTimeout(timer);
    if(observer)observer.disconnect();
    window.removeEventListener('resize',refresh);
    button.removeEventListener('click',click);
    button.remove();
  };
})();
</script>
"""
    return markup.replace("__COMMAND__", str(int(command)))
