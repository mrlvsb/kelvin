# Kelvin

Kelvin - The Ultimate Code Examinator

This repository contains code for Kelvin, a web application designed for sharing lesson
materials with students, submitting lesson/exam code solutions, performing code review,
automatically evaluating submitted code and much more.

An instance of Kelvin used by the Faculty of Electrical Engineering and Computer Science at
VSB-TUO is deployed at `https://kelvin.cs.vsb.cz`.

If you find any bugs in Kelvin or want to suggest new features and improvements, please file an
[issue](https://github.com/mrlvsb/kelvin/issues/new).

You can find documentation of Kelvin's internal workings and how to contribute
in [docs](https://mrlvsb.github.io/kelvin/).
For local documentation, simply: `cd docs && npm ci && npm run start`

## Security

If you find a security vulnerability in Kelvin, please disclose it to kelvin@vsb.cz. Thank
you!

## Contributors

Kelvin is made possible thanks to the contributions of several people. A (non-exhaustive) list of
Kelvin contributors can be found below.

### Maintainers

- [Dan Trnka](https://github.com/trnila) is the original creator of Kelvin.
- [Jan Gaura](https://github.com/geordi) currently maintains Kelvin.
- [Jakub Beránek](https://github.com/kobzol) currently maintains Kelvin.

### Diploma theses

- [Patrik Mintěl](https://github.com/patrick11514) rewrote a part of the frontend from Svelte to Vue
  as a part of
  his [bachelor thesis](https://dspace.vsb.cz/items/e31e48ab-65b7-4437-a33a-023cc7197fb5).
- [Erik Hawlasek](https://github.com/erikhaw) implemented support for quizzes as a part of
  his [master thesis](https://dspace.vsb.cz/items/bf36b333-2d6c-417d-8f1d-5e7f2a5bf3d3).
- [Dominik Lichnovský](https://github.com/JersyJ) currently works on improving Kelvin's deployment
  and CI/CD as a part of his master thesis.
- [Pavel Mikula](https://github.com/Firestone82) currently works on adding AI-powered code reviews
  to
  Kelvin as a part of his master thesis.
- [Šimon Adámek](https://github.com/SimonAdamek) currently works on adding "anti-cheats" and various
  other improvements to Kelvin as a part of his bachelor thesis.

### Other contributors

- [Roman Táborský](https://github.com/Astra3) implemented support for dark mode and theme switching.
- [Jan Dymáček](https://github.com/Dym03) implemented support for task types, relative deadlines and
  hard dedlines.
- [Daniel Krásný](https://github.com/DanielKrasny) implemented storage of IP addresses of submits
  and made various improvements around the test runner script, the clang-tidy workflow, and various
  parts of the web frontend.

Various other people also contributed to Kelvin. The full list can be
found [here](https://github.com/mrlvsb/kelvin/graphs/contributors).

## License
[MIT](LICENSE)
