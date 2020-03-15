axios.defaults.headers.common = {
  "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content,
};

Vue.component('submit-source-comment', {
  props: ['id', 'author', 'text', 'canEdit', 'editComment'],
  template: `
  <div>
    <span style="background: yellow" v-on:dblclick="editing = canEdit">
      <b>{{ author }}</b>: 
      <span v-if="!editing">{{ text }}</span>
    </span>
    <div v-if="editing">
      <textarea class="form-control">{{ text }}</textarea>
      <input type="submit" class="btn btn-sm btn-primary" v-on:click="edit(id, $event.target.closest('td').querySelector('textarea'))">
    </div>
  </div>
  `,
  data() {
    return {
      editing: false,
    };
  },
  methods: {
    edit(id, textarea) {
      let text = textarea.value;
      textarea.value = '';

      this.editComment(id, text).then((resp) => {
          this.editing = false;
      });
    }
  }
});

Vue.component('submit-source', {
  template: `
  <table class="sourcecode">
    <template v-for="(line, linenum) in lines">
      <tr>
        <td>
          {{ linenum + 1 }}
          <span class="comment-add" v-on:click="showForm(linenum + 1)"></span>
        </td>
        <td><pre v-html="line.content"></pre></td>
      </tr>

      <tr v-for="(comment, index) in line.comments">
        <td></td>
        <td>
          <submit-source-comment :id="comment.id" :author="comment.author" :text="comment.text" :canEdit="comment.can_edit" :editComment="editComment" />
        </td>
      </tr>

      <tr v-if="canShowForm(linenum + 1)">
        <td></td>
        <td>
          <div class="form-group">
            <textarea class="form-control mb-1"></textarea>
            <input type="submit" class="btn btn-sm btn-primary" v-on:click="addComment(linenum + 1, $event.target.closest('td').querySelector('textarea'))">
          </div>
        </td>
      </tr>
    </template>
  </table>
</div>
`,
  data() { 
    return {
      formLine: -1,
    }
  },
  props: ['lines', 'source', 'url'],
  methods: {
    canShowForm(linenum) {
      return /*this.lines[linenum - 1].comments.length > 0 ||*/ this.formLine == linenum;
    },

    showForm(linenum) {
      this.formLine = linenum;
    },

    addComment(linenum, textarea) {
      let text = textarea.value;
      if(text.length <= 0) {
        return;
      }

      textarea.disabled = 'disabled';
      axios.post(this.url, {
        text: text,
        source: this.source,
        line: linenum
      }).then((resp) => {
        this.formLine = -1;
        this.lines[linenum - 1].comments.push(resp.data);
      });
    },
    editComment(id, text) {
      return axios.patch(this.url, {
        id: id,
        text: text,
      }).then((resp) => {
        for(var linenum in this.lines) {
          let comments = this.lines[linenum].comments;
          let offset = comments.findIndex((comment) => comment.id == id);
          if(offset >= 0) {
            if(!resp.data) {
              comments.splice(offset, 1);
            } else {
              comments[offset].text = text;
            }
            return;
          }
        }
      });
    },
  }
});

Vue.component('submit-sources', {
  props: ['url'],
  data() {
    return {
      sources: {},
    };
  },
  template: `
  <div>
    <div v-for="content, path in sources">
      <h4>{{ path }} </h4>
      <submit-source :lines="content" :source="path" :url="url" />
    </div>
  </div>`,
  mounted() {
    axios.get(this.url)
      .then((response) => {
          this.sources = response.data
      })
  },
});

new Vue({
  el: '#submit-sources',
})
