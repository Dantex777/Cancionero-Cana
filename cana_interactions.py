"""Controles de navegador para Cancionero Caná v0.4.1.

Sólo inyecta código estático de confianza. No lee tokens, secretos ni datos
privados de Notion. Requiere Streamlit >= 1.52 (st.html con JavaScript).
"""

AUTO_SCROLL_HTML = r"""
<style>
.cana-scroll-toolbar{display:flex;align-items:center;gap:.35rem;background:#222330;
border:1px solid #45435d;border-radius:9px;padding:.35rem .5rem;margin:.3rem 0 .75rem;color:#eee;}
.cana-scroll-toolbar label{font-weight:700;font-size:.84rem;white-space:nowrap;}
.cana-scroll-toolbar select{flex:1;min-width:0;max-width:190px;padding:.34rem;
color:#f4f2f8;background:#191a23;border:1px solid #55516c;border-radius:6px;}
.cana-scroll-toolbar button{color:#fff;background:#363548;border:1px solid #706b88;
border-radius:6px;min-width:34px;min-height:34px;cursor:pointer;}
.cana-scroll-toolbar button:disabled{opacity:.45;cursor:default;}
.cana-song.cana-auto-active{max-height:70dvh;overflow-y:auto;
overscroll-behavior:contain;-webkit-overflow-scrolling:touch;scrollbar-width:thin;}
@media(max-width:640px){
.cana-scroll-toolbar{gap:.25rem;padding:.3rem;}
.cana-scroll-toolbar label{font-size:.78rem;}
.cana-scroll-toolbar select{font-size:.78rem;}
.cana-song.cana-auto-active{max-height:65dvh;}
}
</style>
<div class="cana-scroll-toolbar" id="cana-autoscroll-toolbar" role="group" aria-label="Desplazamiento automático">
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
  const speeds=[0,6,10,16,24,34,47,64];
  let velocity=0, running=false, frameId=null, previous=null;
  const subscriptions=[];
  const viewer=()=>document.querySelector('.cana-song');
  const listen=(node,event,handler,options)=>{
    node.addEventListener(event,handler,options);
    subscriptions.push(()=>node.removeEventListener(event,handler,options));
  };
  function sync(){play.disabled=!velocity;play.textContent=running?'Ⅱ':'▶';
    play.setAttribute('aria-label',running?'Pausar':'Reanudar');}
  function pause(){running=false;previous=null;
    if(frameId!==null)cancelAnimationFrame(frameId);frameId=null;sync();}
  function tick(time){
    if(!running)return;
    const target=viewer();
    if(!target){pause();return;}
    if(previous!==null){
      const seconds=Math.min((time-previous)/1000,.08);
      target.scrollTop+=speeds[velocity]*seconds;
      if(target.scrollTop+target.clientHeight>=target.scrollHeight-2){pause();return;}
    }
    previous=time;frameId=requestAnimationFrame(tick);
  }
  function start(){
    const target=viewer();
    if(!velocity||!target)return;
    target.classList.add('cana-auto-active');
    if(target.scrollHeight<=target.clientHeight+1){pause();return;}
    if(frameId!==null)cancelAnimationFrame(frameId);
    running=true;previous=null;sync();frameId=requestAnimationFrame(tick);
  }
  function onSpeed(){
    velocity=Number(selector.value)||0;
    const target=viewer();
    if(!velocity){pause();if(target)target.classList.remove('cana-auto-active');}
    else start();
  }
  function backToStart(){
    pause();velocity=0;selector.value='0';
    const target=viewer();
    if(target){target.scrollTop=0;target.classList.remove('cana-auto-active');}
  }
  function userInteracts(e){
    const target=viewer();
    if(target&&target.contains(e.target))pause();
  }
  listen(selector,'change',onSpeed);
  listen(play,'click',()=>running?pause():start());
  listen(reset,'click',backToStart);
  listen(document,'pointerdown',userInteracts,{passive:true});
  listen(document,'touchstart',userInteracts,{passive:true});
  listen(document,'wheel',userInteracts,{passive:true});
  listen(document,'visibilitychange',()=>{if(document.hidden)pause();});
  listen(document,'keydown',e=>{
    if(['ArrowDown','ArrowUp','PageDown','PageUp',' '].includes(e.key))pause();
  });
  sync();
  window.__canaScrollCleanup=()=>{
    pause();subscriptions.forEach(unsubscribe=>unsubscribe());
  };
})();
</script>
"""


def sidebar_helper_html(command: int) -> str:
    """Cierre móvil best-effort; usa controles existentes del frontend."""
    html = r"""
<style>
.cana-mobile-close{display:none;position:fixed;top:12px;right:12px;z-index:999999;
color:#fff;background:#333349;border:1px solid #a99bd3;border-radius:9px;
padding:7px 10px;font:600 12px system-ui,sans-serif;cursor:pointer;}
@media(max-width:820px){.cana-mobile-close[data-open="true"]{display:block;}}
</style>
<div id="cana-sidebar-command" data-counter="__COUNTER__" hidden></div>
<script>
(()=>{
  if(window.__canaMenuCleanup)window.__canaMenuCleanup();
  const source=document.getElementById('cana-sidebar-command');
  if(!source)return;
  const command=Number(source.dataset.counter||0);
  const sidebar=()=>document.querySelector('[data-testid="stSidebar"]');
  const isExpanded=()=>{
    const node=sidebar();
    if(!node)return false;
    const collapsed=node.getAttribute('data-collapsed');
    if(collapsed==='true')return false;
    if(collapsed==='false')return true;
    const box=node.getBoundingClientRect();
    return box.width>90&&box.right>20&&box.left<window.innerWidth-20;
  };
  function close(){
    const sb=sidebar();if(!sb||!isExpanded())return true;
    const wrappers=[...sb.querySelectorAll('[data-testid="stSidebarCollapseButton"]')];
    const buttons=wrappers.map(w=>w.matches('button')?w:w.querySelector('button'));
    buttons.push(...sb.querySelectorAll('button[aria-label],button[title]'));
    const toggle=buttons.find(b=>b&&(
      b.closest('[data-testid="stSidebarCollapseButton"]')||
      /collapse sidebar|close sidebar|cerrar (menú|barra)|ocultar barra|colapsar/i.test(
        (b.getAttribute('aria-label')||'')+' '+(b.getAttribute('title')||''))
    ));
    if(!toggle)return false;
    toggle.click();return true;
  }
  let button=document.getElementById('cana-floating-close');
  if(!button){button=document.createElement('button');button.id='cana-floating-close';
    button.className='cana-mobile-close';button.type='button';
    button.textContent='✕ Cerrar menú';document.body.appendChild(button);}
  const onClose=()=>close();
  button.addEventListener('click',onClose);
  const refresh=()=>{button.dataset.open=isExpanded()?'true':'false';};
  let observer=null,timer=null;
  if(sidebar()){observer=new MutationObserver(refresh);
    observer.observe(sidebar(),{attributes:true,attributeFilter:['style','class','data-collapsed']});}
  window.addEventListener('resize',refresh);
  refresh();
  if(command>0&&window.__canaLastCloseCommand!==command){
    window.__canaLastCloseCommand=command;
    let attempts=0;
    const attempt=()=>{
      attempts++;
      if(isExpanded()&&!close()&&attempts<6)timer=setTimeout(attempt,160);
      refresh();
    };
    timer=setTimeout(attempt,200);
  }
  window.__canaMenuCleanup=()=>{
    if(timer)clearTimeout(timer);
    if(observer)observer.disconnect();
    window.removeEventListener('resize',refresh);
    button.removeEventListener('click',onClose);
    button.remove();
  };
})();
</script>
"""
    return html.replace("__COUNTER__", str(int(command)))
