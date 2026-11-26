<!--
Check each claim below against r9lab-vocabulary before you publish it, and reword or
delete any that does not hold. The template writes these claims; it does not test them.
-->

# Accessibility

r9lab-vocabulary is a command-line program with one web page, for rating the tag mappings.

## Command line

The commands should work with a screen reader, in a terminal without colour, and in scripts and CI logs:

- Colour is never the only signal. A coloured message also says in words what it means,
  such as `error:` or `warning:`.
- It prints no colour when the [`NO_COLOR`](https://no-color.org) environment variable is
  set or when you pass `--color never`.
- When its output is not a terminal, such as a pipe, a file or a CI log, it prints plain
  lines, with no spinners, progress bars or cursor movement.
- It writes errors to standard error, and an error about a file names the place as
  `file:line:col`, so an editor or a screen reader can jump to it.

## Review page

The page `just review` serves aims at WCAG 2.2 AA:

- Every action works from the keyboard: Tab reaches each button, and `a`, `u`, `d`, `z` and `p`
  give a verdict, undo and pause. The keys ignore Ctrl, Alt and Meta, so browser shortcuts are
  left alone.
- Text has at least 4.5:1 contrast and button borders at least 3:1, in light and dark mode. It
  uses the system colours, so a forced-colours or high-contrast mode applies.
- After each verdict, focus moves to the new card's tag, and a status line says what was
  recorded.
- It works without JavaScript, as plain form posts, Undo included; the keys and Pause need it.

## Contact

If r9lab-vocabulary is hard to use with your setup, email <code@duinlab.nl>. Say what
you tried, what you use (terminal, screen reader, operating system) and what happened.
