Primary action button — orange `primary` is the single key action per view; use `secondary`/`ghost`/`dark` for the rest.

```jsx
<Button variant="primary" onClick={save}>Enviar</Button>
<Button variant="secondary">Cancelar</Button>
<Button variant="ghost" size="sm">Ver más</Button>
<Button variant="dark" iconRight={<i data-lucide="arrow-right" />}>Continuar</Button>
```

Variants: `primary` (orange), `secondary` (gray outline), `ghost` (orange text), `dark` (ink). Sizes: `sm` / `md` / `lg`. Supports `disabled`, `iconLeft`, `iconRight`.
