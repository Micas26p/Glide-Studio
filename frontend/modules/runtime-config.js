(function(){
  async function loadConfig(){
    const response = await fetch('/api/config', {cache: 'no-store'});
    if(!response.ok) throw new Error(await response.text());
    return response.json();
  }

  function warmCache(){
    return fetch('/api/warm-cache', {method: 'POST', cache: 'no-store'}).catch(() => null);
  }

  window.GlideRuntime = {loadConfig, warmCache};
})();
