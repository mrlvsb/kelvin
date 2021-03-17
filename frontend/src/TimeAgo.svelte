<script>
  import { format } from 'timeago.js';
  export let datetime;
  export let rel = null;
  export let suffix = null;
  export let prefix = null;
</script>

<script context="module">
  import { register } from 'timeago.js';

  register('en_num', (number, index) => {
    return [
      ['0 seconds', '0 seconds'],
      ['%s seconds', '%s seconds'],
      ['1 minute', '1 minute'],
      ['%s minutes', '%s minutes'],
      ['1 hour', '1 hour'],
      ['%s hours', '%s hours'],
      ['1 day', '1 day'],
      ['%s days', '%s days'],
      ['1 week', '1 week'],
      ['%s weeks', '%s weeks'],
      ['1 month', '1 month'],
      ['%s months', '%s months'],
      ['1 year', '1 year'],
      ['%s years', '%s years']
    ][index];
  });
</script>

<time datetime={new Date(datetime).toISOString()} title={new Date(datetime).toLocaleString('cs')}>
  {prefix ? prefix : ''} {format(new Date(datetime), prefix !== null || suffix !== null ? 'en_num' : null, {relativeDate: rel})} {suffix ? suffix : ''}
</time>