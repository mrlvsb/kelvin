axios.defaults.headers.common = {
  "X-CSRFToken": document.querySelector('meta[name="csrf-token"]').content,
};

Vue.component('submit-source-form', {
  props: ['save', 'text', 'required'],
  template: `
  <form>
      <textarea class="form-control mb-1" v-on:keydown="keydown($event)" ref="text" :disabled="sending" style="line-height: 100%" rows=4>{{ text }}</textarea>
      <input type="submit" class="btn btn-sm btn-primary" v-on:click="submit" :disabled="sending" value='Send'>
  </form>`,
  data() {
    return {
      sending: false,
    };
  }, 
  methods: {
    keydown(evt) {
      if (evt.ctrlKey && evt.keyCode == 13) {
        this.submit();
      }
    },

    submit() {
      let value = this.$refs.text.value;
      if(this.required && value.length <= 0) {
        return;
      }
      this.sending = true;
      this.save(value);
    }
  }
});

Vue.component('submit-source-comment', {
  props: ['id', 'author', 'text', 'canEdit', 'type', 'editComment'],
  template: `
  <div class="comment" :class="type">
    <span v-on:dblclick="editing = canEdit">
      <b>{{ author }}</b>: <span v-if="!editing">{{ text }}</span>
    </span>
    <div v-if="editing">
      <submit-source-form :save="edit" :text="text" /> 
    </div>
  </div>
  `,
  data() {
    return {
      editing: false,
    };
  },
  methods: {
    edit(text) {
      this.editComment(this.id, text).then((resp) => {
          this.editing = false;
      });
    }
  }
});

Vue.component('submit-source', {
  template: `
  <table class="sourcecode">
    <template v-for="(line, lineIdx) in lines">
      <tr>
        <td>
          {{ lineIdx + 1 }}
          <span class="comment-add" v-on:click="showForm(lineIdx)"></span>
        </td>
        <td><pre v-html="line.content"></pre></td>
      </tr>

      <tr v-for="(comment, index) in line.comments">
        <td></td>
        <td>
          <submit-source-comment
              :id="comment.id"
              :author="comment.author"
              :text="comment.text"
              :canEdit="comment.can_edit"
              :type="comment.type"
              :editComment="editComment" />
        </td>
      </tr>

      <tr v-if="lineIdx == formLineIdx">
        <td></td>
        <td>
          <div class="form-group">
            <submit-source-form :save="addComment" :required="true" /> 
          </div>
        </td>
      </tr>
    </template>
  </table>
`,
  data() { 
    return {
      formLineIdx: -1,
    }
  },
  props: ['lines', 'source', 'url'],
  methods: {
    showForm(lineidx) {
      this.formLineIdx = lineidx;
    },

    addComment(text) {
      if(text.length <= 0) {
        return;
      }

      axios.post(this.url, {
        text: text,
        source: this.source,
        line: this.formLineIdx + 1
      }).then((resp) => {
        this.lines[this.formLineIdx].comments.push(resp.data);
        this.formLineIdx = -1;
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
    <div v-for="type in sources">
      <div class="submit-file-header">
        <h4 style="margin: 0">{{ type.path }} </h4>
        <i class="fas fa-copy icon copy"
           style="color: #007bff; cursor: pointer"
           title="Copy file content into clipboard"
           v-if="type.content"
           :data-clipboard-text="type.content"></i>
      </div>
      <submit-source :lines="type.lines" :source="type.path" :url="url" v-if="type.type == 'source'" />
      <img :src="type.src" v-if="type.type == 'img'" />
      <video v-if="type.type == 'video'" controls>
        <source :src="src" v-for="src in type.sources"></source>
      </video>
    </div>
  </div>`,
  mounted() {
    axios.get(this.url)
      .then((response) => {
          this.sources = response.data
      })
  },
});

document.querySelectorAll('.comments').forEach((el) => {
  new Vue({
    el: el,
  })
});
