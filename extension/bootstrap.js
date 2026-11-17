/* ES5: display startup and host failures beside the first button. */
(function(){
 window.SVEPanelError=function(error){
  var L=window.SVEi18n,message=error&&error.message?error.message:String(error);if(L)message=L.tr(message);
  var output=document.getElementById('clip');
  if(output){output.textContent=L?L.t('error',message):'Xato: '+message;output.style.color='#ffb5a8';output.setAttribute('role','alert');}
 };
 window.addEventListener('error',function(event){window.SVEPanelError(event.error||event.message);});
 window.addEventListener('unhandledrejection',function(event){window.SVEPanelError(event.reason);});
 window.addEventListener('load',function(){if(!window.SVEPanelReady)window.SVEPanelError(window.SVEi18n?window.SVEi18n.t('panelNotLoaded'):'Panel kodi yuklanmadi. Premiere va panelni qayta oching.');});
})();
