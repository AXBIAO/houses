// 与 src/theme/theme.ts 的 resolveAppTheme 保持同步：存储值 → 系统偏好 → 浅色。
// 独立成文件（而非内联）是为了让 CSP 可以只允许同源脚本；放在 head 里同步加载，首帧前就确定主题，避免闪烁。
(function () {
  try {
    var t = localStorage.getItem('app_theme');
    if (t !== 'light' && t !== 'dark') {
      t = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    if (t === 'dark') document.documentElement.setAttribute('data-theme', 'dark');
  } catch (e) { /* 存储被禁用时默认浅色 */ }
})();
