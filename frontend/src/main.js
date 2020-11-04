function createElement(name, component) {
	customElements.define('kelvin-' + name, class extends HTMLElement {
		connectedCallback() {
			let attrs = {};
			for(let i = 0; i < this.attributes.length; i++) {
				let attr = this.attributes[i];
				let name = attr.name.replace('-', '_')
				if(attr.value[0] == '{' || attr.value[0] == '[') {
					attrs[name] = JSON.parse(attr.value);
				} else {
					attrs[name] = attr.value;
				}
			}

			new component({
				target: this,
				props: attrs,
			})
		}
	});
}

createElement('app', require('./App.svelte'));
createElement('submit-sources', require('./TaskDetail.svelte'));
