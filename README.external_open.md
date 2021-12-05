# Open submit on desktop app

1. create schema handler for `kelvin:`:
   ```
   # ~/.local/share/applications/kelvin-open.desktop
   [Desktop Entry]
   Type=Application
   Name=Kelvin schema handler
   Exec=kelvin-open %u
   StartupNotify=false
   MimeType=x-scheme-handler/kelvin;
   ```

2. register schema with default app

   ```sh
   $ xdg-mime default kelvin.desktop x-schema-handler/kelvin
   ```
3. <a href="https://kelvin.cs.vsb.cz/api_token">generate your API token</a> and store it in `~/.config/kelvin/token`

4. create your `kelvin-open` script and add it to the `$PATH`
   ```
   #!/bin/bash
   cd $(mktemp -d)

   # download submit
   url=$(echo $1 | sed 's/kelvin://')
   curl -H"Authorization: Bearer $(<~/.config/kelvin/token)" $url | tar xvz

   # uncomment one exec line below:
   #exec gnome-terminal
   #exec code .

   # start in ubuntu container
   #exec gnome-terminal -- docker run --rm -v $PWD:/submit -w /submit -it ubuntu bash

   # start in ubuntu container with X11 forwarding (xhost + or something like that required on your side)
   #exec gnome-terminal -- docker run --rm -v $PWD:/submit -w /submit -v /tmp:/tmp -e DISPLAY=:0 -it ubuntu bash
   ```

