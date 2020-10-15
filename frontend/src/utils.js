export function clickOutside(node) {
  const handleClick = event => {
    if (node && !node.contains(event.target) && !event.defaultPrevented) {
      node.dispatchEvent(
        new CustomEvent('click_outside', node)
      )
    }
  }

  document.addEventListener('click', handleClick, true);

  return {
    destroy() {
      document.removeEventListener('click', handleClick, true);
    }
  }
}

export function timeInWords(milliseconds) {
  function numberEnding (number) {
    return (number > 1) ? 's' : '';
  }

  var temp = Math.floor(Math.abs(milliseconds) / 1000);
  var years = Math.floor(temp / 31536000);
  if (years) {
    return years + ' year' + numberEnding(years);
  }
  var days = Math.floor((temp %= 31536000) / 86400);
  if (days) {
    return days + ' day' + numberEnding(days);
  }
  var hours = Math.floor((temp %= 86400) / 3600);
  if (hours) {
    return hours + ' hour' + numberEnding(hours);
  }
  var minutes = Math.floor((temp %= 3600) / 60);
  if (minutes) {
    return minutes + ' minute' + numberEnding(minutes);
  }
  var seconds = temp % 60;
  if (seconds) {
    return seconds + ' second' + numberEnding(seconds);
  }
  return 'less than a second';
}

export function formatDateTime(date) {
  function pad(n) {
    return n<10 ? '0'+n : n;
  }

  const jsDate = new Date(date);

  return `${jsDate.toLocaleDateString('cs-CZ')} ${pad(jsDate.getHours())}:${pad(jsDate.getMinutes())}`;
}
