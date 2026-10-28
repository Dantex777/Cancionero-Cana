"""Interacciones del Cancionero Caná v0.4.3.

El visor autocontenido evita buscar la letra en otros elementos de Streamlit.
El HTML musical es generado por musica.render_song, que escapa el texto de Notion.
"""
AUTO_SCROLL_WRAPPER = r"""
<style>
#cana-scroll-root .cana-scroll-toolbar{
  display:flex;align-items:center;gap:.36rem;flex-wrap:wrap;
  background:#222330;border:1px solid #45435d;border-radius:9px;
  padding:.35rem .55rem;margin:.25rem 0 .75rem;color:#eee;
}
#cana-scroll-root .cana-scroll-toolbar label{
  font-weight:700;font-size:.83rem;white-space:nowrap;
}
#cana-scroll-root .cana-scroll-toolbar select{
  flex:1;min-width:100px;max-width:185px;padding:.4rem;
  color:#f4f2f8;background:#191a23;border:1px solid #55516c;border-radius:6px;
}
#cana-scroll-root .cana-scroll-toolbar button{
  color:#fff;background:#363548;border:1px solid #706b88;
  border-radius:6px;min-width:35px;min-height:35px;cursor:pointer;
}
#cana-scroll-root .cana-scroll-toolbar button:disabled{opacity:.45;cursor:default;}
#cana-scroll-root .cana-scroll-status{
  color:#bebbd1;font-size:.73rem;
}
#cana-scroll-root .cana-song.cana-auto-active{
  height:65dvh;min-height:250px;max-height:65dvh;
  overflow-y:auto!important;overflow-x:auto;
  overscroll-behavior:contain;-webkit-overflow-scrolling:touch;
  scrollbar-width:thin;scroll-behavior:auto!important;
}
@media(max-width:640px){
  #cana-scroll-root .cana-scroll-toolbar{gap:.25rem;padding:.3rem;}
  #cana-scroll-root .cana-scroll-toolbar label{font-size:.78rem;}
  #cana-scroll-root .cana-scroll-toolbar select{max-width:148px;font-size:.78rem;}
  #cana-scroll-root .cana-song.cana-auto-active{
    height:62dvh;max-height:62dvh;
  }
}
</style>
<section id="cana-scroll-root" aria-label="Visor de canciones con desplazamiento automático">
  <div class="cana-scroll-toolbar" role="group" aria-label="Auto Scroll">
    <label for="cana-scroll-speed">Auto Scroll</label>
    <select id="cana-scroll-speed" aria-label="Velocidad del Auto Scroll">
      <option value="0">Apagado</option>
      <option value="1">1 · Muy lento</option><option value="2">2</option>
      <option value="3">3</option><option value="4">4</option>
      <option value="5">5</option><option value="6">6</option>
      <option value="7">7 · Rápido</option>
    </select>
    <button id="cana-scroll-play" type="button" aria-label="Pausar o reanudar" disabled>▶</button>
    <button id="cana-scroll-reset" type="button" aria-label="Reiniciar desde el principio">↺</button>
    <span id="cana-scroll-status" class="cana-scroll-status" aria-live="polite">Apagado</span>
  </div>
  __SONG_HTML__
</section>
<script>
(()=>{
  if(window.__canaScrollCleanup)window.__canaScrollCleanup();
  const root=document.getElementById('cana-scroll-root');
  if(!root)return;
  const viewer=root.querySelector('.cana-song');
  const select=root.querySelector('#cana-scroll-speed');
  const play=root.querySelector('#cana-scroll-play');
  const reset=root.querySelector('#cana-scroll-reset');
  const status=root.querySelector('#cana-scroll-status');
  if(!viewer||!select||!play||!reset)return;
  // Escala lenta en píxeles por segundo: cada paso conserva fracciones.
  const rates=[0,3,4,6,8,10,13,16];
  let level=0,playing=false,frame=0,lastTime=0,exactPosition=0;
  const unsub=[];
  const on=(node,name,fn,opts)=>{
    node.addEventListener(name,fn,opts);
    unsub.push(()=>node.removeEventListener(name,fn,opts));
  };
  const setLabel=(label)=>{status.textContent=label;};
  const updateButton=()=>{
    play.disabled=level===0;
    play.textContent=playing?'Ⅱ':'▶';
    play.setAttribute('aria-label',playing?'Pausar Auto Scroll':'Continuar Auto Scroll');
  };
  const pause=(label='Pausado')=>{
    playing=false;
    if(frame)cancelAnimationFrame(frame);
    frame=0;lastTime=0;
    if(level)setLabel(label);
    updateButton();
  };
  const advance=(timestamp)=>{
    if(!playing)return;
    const max=Math.max(0,viewer.scrollHeight-viewer.clientHeight);
    if(lastTime){
      // Guardamos el decimal independientemente del redondeo del navegador.
      const delta=Math.max(0,Math.min(.10,(timestamp-lastTime)/1000));
      exactPosition=Math.min(max,exactPosition+rates[level]*delta);
      viewer.scrollTop=exactPosition;
      if(exactPosition>=max-.1){pause('Fin del canto');return;}
    }
    lastTime=timestamp;
    frame=requestAnimationFrame(advance);
  };
  const start=()=>{
    if(!level)return;
    viewer.classList.add('cana-auto-active');
    const max=viewer.scrollHeight-viewer.clientHeight;
    if(max<=1){pause('No hay más contenido que desplazar');return;}
    if(viewer.scrollTop>=max-1)viewer.scrollTop=0;
    exactPosition=viewer.scrollTop;
    lastTime=0;
    if(frame)cancelAnimationFrame(frame);
    playing=true;
    setLabel('Avanzando · '+level+'/7');
    updateButton();
    frame=requestAnimationFrame(advance);
  };
  const speedChanged=()=>{
    level=Number(select.value)||0;
    if(!level){
      pause('Apagado');
      viewer.classList.remove('cana-auto-active');
      viewer.scrollTop=0;
      setLabel('Apagado');
    }else start();
    updateButton();
  };
  const restart=()=>{
    pause();
    level=0;select.value='0';
    viewer.scrollTop=0;
    viewer.classList.remove('cana-auto-active');
    setLabel('Apagado');
    updateButton();
  };
  const touchToPause=()=>{
    if(playing)pause('Pausado al tocar');
    exactPosition=viewer.scrollTop;
  };
  on(select,'change',speedChanged);
  on(play,'click',()=>playing?pause():start());
  on(reset,'click',restart);
  on(viewer,'pointerdown',touchToPause,{passive:true});
  on(viewer,'touchstart',touchToPause,{passive:true});
  on(viewer,'wheel',touchToPause,{passive:true});
  on(document,'visibilitychange',()=>{if(document.hidden)pause();});
  on(document,'keydown',ev=>{
    if(playing&&['ArrowDown','ArrowUp','PageDown','PageUp',' '].includes(ev.key))
      pause('Pausado al usar teclado');
  });
  updateButton();
  window.__canaScrollCleanup=()=>{
    pause();unsub.forEach(fn=>fn());
  };
})();
</script>
"""

def render_autoscroll_song(song_html: str) -> str:
    """Inject song HTML built by musica.render_song (escaped Notion text)."""
    return AUTO_SCROLL_WRAPPER.replace("__SONG_HTML__", song_html)


def sidebar_helper_html(command: int) -> str:
    """Intenta cerrar la barra sólo después de seleccionar canción o catálogo.

    Streamlit expone el estado en aria-expanded, pero no tiene API pública
    para cambiarlo desde Python. Se pulsa el botón nativo y se comprueba si
    realmente cambió. No se cambia el estilo de la barra a la fuerza.
    """
    markup = r"""
<style>
@media(max-width:820px){
  [data-testid="stSidebarCollapseButton"]{
    position:fixed!important;top:12px!important;right:12px!important;
    z-index:999999!important;opacity:1!important;visibility:visible!important;
  }
  [data-testid="stSidebarCollapseButton"] button{
    background:#34344b!important;border-radius:10px!important;
    box-shadow:0 2px 8px #0009!important;
  }
}
</style>
<div id="cana-close-command" data-command="__COMMAND__" hidden></div>
<script>
(()=>{
  if(window.__canaMenuCleanup)window.__canaMenuCleanup();
  const marker=document.getElementById('cana-close-command');
  if(!marker)return;
  const command=Number(marker.dataset.command||0);
  let cancelled=false, timer=null;
  const sidebar=()=>document.querySelector('[data-testid="stSidebar"]');
  const expanded=()=>{
    const node=sidebar();
    if(!node)return false;
    const attr=node.getAttribute('aria-expanded');
    if(attr==='true')return true;
    if(attr==='false')return false;
    return node.getBoundingClientRect().width>90;
  };
  const nativeButton=()=>{
    const root=document.querySelector('[data-testid="stSidebarCollapseButton"]');
    if(!root)return null;
    return root.matches('button')?root:root.querySelector('button');
  };
  function checkClose(attempt=0){
    if(cancelled||!expanded()||attempt>=5)return;
    const button=nativeButton();
    if(button){
      button.click();
      // IMPORTANTE: el clic no garantiza el cierre. Esperar la actualización
      // de React antes de decidir si hay que volver a intentar.
      timer=setTimeout(()=>{
        if(!cancelled&&expanded())checkClose(attempt+1);
      },550);
    }else{
      // El botón nativo puede montarse después del resto del visor.
      timer=setTimeout(()=>checkClose(attempt+1),250);
    }
  }
  if(command>0&&window.__canaLastCloseCommand!==command){
    window.__canaLastCloseCommand=command;
    // Espera a que termine el render del nuevo canto o catálogo.
    timer=setTimeout(()=>checkClose(),350);
  }
  window.__canaMenuCleanup=()=>{
    cancelled=true;
    if(timer!==null)clearTimeout(timer);
  };
})();
</script>
"""
    return markup.replace("__COMMAND__", str(int(command)))
