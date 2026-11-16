/* ES5: display startup and host failures beside the first button. */
(function(){
 window.SVEPanelError=function(error){
  var message=error&&error.message?error.message:String(error);
  var output=document.getElementById('clip');
  if(output){output.textContent='Xato: '+message;output.style.color='#ffb5a8';output.setAttribute('role','alert');}
 };
 window.addEventListener('error',function(event){window.SVEPanelError(event.error||event.message);});
 window.addEventListener('unhandledrejection',function(event){window.SVEPanelError(event.reason);});
 window.addEventListener('load',function(){if(!window.SVEPanelReady)window.SVEPanelError('Panel kodi yuklanmadi. Premiere va panelni qayta oching.');});
})();
