The "corporativo." logo — full wordmark with the orange infinity "co" ligature, gray lettering, and final orange period. Embedded as data URIs (self-contained).

```jsx
<Logo height={36} />                      {/* positive — on light */}
<Logo variant="negative" height={36} />   {/* white lettering — on dark */}
<Logo variant="white" height={36} />      {/* all white — on orange/colored */}
<Logo markOnly height={24} />             {/* infinity mark — favicon sizes only */}
```

Rules: never deform, rotate, or recolor; mark alone only at favicon/app-icon sizes. Source PNGs in `assets/corporativo-logo*.png`.
