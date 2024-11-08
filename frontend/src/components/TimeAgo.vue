<script setup lang="ts">
import { register, format } from 'timeago.js';

register('en_num', (_, index) => {
  return (
    [
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
    ] satisfies [string, string][]
  )[index];
});

defineProps<{
  datetime: string;
  rel?: string;
  suffix?: string;
  prefix?: string;
}>();
</script>

<template>
  <time
    :datetime="new Date(datetime).toISOString()"
    :title="new Date(datetime).toLocaleString('cs')"
  >
    <template v-if="prefix">{{ prefix }}</template
    >{{
      format(
        new Date(datetime),
        prefix !== undefined || suffix !== undefined ? 'en_num' : undefined,
        {
          relativeDate: rel
        }
      )
    }}<template v-if="suffix">{{ suffix }}</template>
  </time>
</template>
