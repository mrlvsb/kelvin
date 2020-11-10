<script>
  import { simple as format } from 'timeago-simple';	
  export let datetime;
</script>

<time datetime={new Date(datetime).toISOString()} title={new Date(datetime).toLocaleString('cs')}>
  {format(new Date(datetime))}
</time>