(function () {
  var t = null
  try { t = localStorage.getItem('theme') } catch (e) {}
  if (t === 'dark' || (!t && window.matchMedia('(prefers-color-scheme: dark)').matches))
    document.documentElement.classList.add('dark')
})()
