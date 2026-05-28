// 數字格式化工具
window.formatTWD = function(n) {
  if (n == null || n === 0) return '—';
  if (Math.abs(n) >= 1e8) return (n / 1e8).toFixed(2) + ' 億';
  if (Math.abs(n) >= 1e4) return (n / 1e4).toLocaleString(undefined, { maximumFractionDigits: 0 }) + ' 萬';
  return n.toLocaleString();
};

window.formatNT = function(n) {
  if (n == null) return '—';
  return 'NT$ ' + Math.round(n).toLocaleString();
};

window.formatPerPing = function(total, ping) {
  if (!total || !ping || ping < 10) return '—';
  return (total / ping).toLocaleString(undefined, { maximumFractionDigits: 0 });
};
