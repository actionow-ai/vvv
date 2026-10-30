const assert = require('node:assert/strict');
const fs = require('node:fs');
const { test } = require('node:test');
const ts = require('typescript');

// Use the project's compiler, without emitting files or loading a browser.
const compile = (mod, filename) => {
  const { outputText } = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
  });
  mod._compile(outputText, filename);
};
require.extensions['.ts'] = compile;
require.extensions['.tsx'] = compile;

const { createAssetRegistry } = require('./asset-registry.ts');
const { createSlotsSchema } = require('./slot-schema.ts');
const { albumSlots } = require('../templates/album/slots.ts');
const { doodleSlots } = require('../templates/doodle/slots.ts');

const photo = { id: 'project-photo', file: 'photos/photo.jpg', width: 1200, height: 1800, orientation: 'portrait' };
const registry = createAssetRegistry({ version: '0.1', items: [photo] });
const idExists = (id) => { registry.getPhoto(id); };
const inputs = (slots) => Object.fromEntries(Object.entries(slots).map(([key, spec]) => [key, spec.count === undefined ? photo.id : Array(spec.count).fill(photo.id)]));

test('unknown project IDs produce a structured diagnostic and never select another asset', () => {
  assert.throws(() => registry.getPhoto('absent'), { code: 'VVV_ASSET_UNKNOWN' });
  assert.equal(registry.getPhoto(photo.id).file, 'photos/photo.jpg');
});

test('Album rejects an empty gallery before the renderer tries to extend its final shot', () => {
  const props = { ...inputs(albumSlots), gallery: [] };
  const result = createSlotsSchema(albumSlots, idExists).safeParse(props);
  assert.equal(result.success, false);
  assert.deepEqual(result.error.issues[0].path, ['gallery']);
});

test('the exported Album component enforces the input contract before scene hooks', () => {
  const { album } = require('../templates/album/index.tsx');
  assert.throws(() => album.component({ ...album.defaultProps, photos: { ...album.defaultProps.photos, gallery: [] } }), /VVV_INPUT_INVALID:.*photos\.gallery/s);
});

test('Album allows one gallery photo but rejects IDs missing from this project', () => {
  const schema = createSlotsSchema(albumSlots, idExists);
  const valid = { ...inputs(albumSlots), gallery: [photo.id] };
  assert.equal(schema.safeParse(valid).success, true);
  const invalid = schema.safeParse({ ...valid, gallery: ['absent'] });
  assert.equal(invalid.success, false);
  assert.deepEqual(invalid.error.issues[0].path, ['gallery', 0]);
});

test('Doodle rejects short photo arrays that its original scene indexes cannot render', () => {
  const schema = createSlotsSchema(doodleSlots, idExists);
  const valid = inputs(doodleSlots);
  assert.equal(schema.safeParse(valid).success, true);
  for (const key of ['poem', 'forever', 'oneLove', 'ever', 'soul']) {
    const invalid = schema.safeParse({ ...valid, [key]: [] });
    assert.equal(invalid.success, false, key);
    assert.deepEqual(invalid.error.issues[0].path, [key]);
  }
});

test('project manifests reject duplicate IDs and paths outside public', () => {
  assert.throws(() => createAssetRegistry({ version: '0.1', items: [photo, photo] }), { code: 'VVV_ASSET_MANIFEST_INVALID' });
  for (const file of ['../private.jpg', '/outside.jpg', 'https://example.test/photo.jpg', 'photos\\outside.jpg']) {
    assert.throws(() => createAssetRegistry({ version: '0.1', items: [{ ...photo, file }] }), { code: 'VVV_ASSET_MANIFEST_INVALID' });
  }
});

test('gallery timing rejects impossible capacity rather than silently extending its window', () => {
  const { placeShots } = require('../engine/Gallery.tsx');
  const plans = Array.from({ length: 6 }, () => ({ kind: 'full', ids: [photo.id], set: 'project', first: false }));
  assert.throws(() => placeShots(plans, (n) => n, 0, 8, 2), /VVV_TIMELINE_INVALID/);
  const shots = placeShots(plans, (n) => n, 0, 12, 2);
  assert.equal(shots[0].from, 0);
  assert.equal(shots.at(-1).to, 12);
});

test('portrait frames stack gallery layouts inside the frame; landscape layouts are unchanged', () => {
  const { layoutBoxes, ALL_LAYOUTS } = require('../engine/Gallery.tsx');
  const counts = { full: 1, inset: 1, solo: 1, pair: 2, trio: 3, hero: 3, mixed: 2, offset: 2, strip: 4 };
  for (const kind of ALL_LAYOUTS) {
    for (const flip of [false, true]) {
      const boxes = layoutBoxes(kind, counts[kind], 64, 28, 1080, 1920, 150, flip, 1.5);
      assert.equal(boxes.length, counts[kind], kind);
      for (const b of boxes) {
        assert.ok(b.w > 0 && b.h > 0, `${kind} has an empty box`);
        assert.ok(b.x >= 0 && b.y >= 0 && b.x + b.w <= 1080 + 0.5 && b.y + b.h <= 1920 + 0.5, `${kind} leaves the 9:16 frame`);
      }
    }
  }
  // Portrait pairs sit side by side but no taller than a readable portrait print.
  const [a, b] = layoutBoxes('pair', 2, 64, 28, 1080, 1920, 150);
  assert.ok(a.h / a.w <= 1 / 0.7 + 1e-9 && b.x > a.x);
  // A trio leads with one wide photo over two smaller ones.
  const trio = layoutBoxes('trio', 3, 64, 28, 1080, 1920, 150);
  assert.ok(trio[0].w > trio[1].w && trio[1].y > trio[0].y);
  // The 16:9 path is the original layout code: a pair stays on one row.
  const wide = layoutBoxes('pair', 2, 84, 36, 1920, 1080, 72);
  assert.equal(wide[0].y, wide[1].y);
  assert.equal(wide[0].h, 1080 - 2 * 72);
});

test('every catalog file has a registered template with the same composition ID, and vice versa', () => {
  const path = require('node:path');
  const { TEMPLATES, frameFor } = require('../templates/index.ts');
  const dir = path.join(__dirname, '..', '..', 'catalog');
  const ids = fs.readdirSync(dir).filter((f) => f.endsWith('.json')).map((f) => f.slice(0, -5)).sort();
  assert.deepEqual(ids, ['album', 'cinema', 'comedy', 'doodle', 'dv-story', 'editorial', 'memoir', 'papercut-frame', 'starter']);
  assert.deepEqual(Object.keys(TEMPLATES).sort(), ids);
  for (const id of ids) {
    const catalog = JSON.parse(fs.readFileSync(path.join(dir, `${id}.json`), 'utf8'));
    assert.equal(TEMPLATES[id].definition.id, catalog.compositionId, id);
    assert.ok(catalog.formats[catalog.defaultFormat], `${id} default format`);
  }
  const starter = TEMPLATES.starter.catalog;
  assert.deepEqual(frameFor(starter, '9:16'), { width: 1080, height: 1920, format: '9:16' });
  assert.deepEqual(frameFor(starter, undefined), { width: 1920, height: 1080, format: '16:9' });
  assert.throws(() => frameFor(starter, '1:1'), /VVV_FORMAT_UNSUPPORTED/);
});

test('shipped wedding fixtures resolve valid props, photos and declared soundtracks', () => {
  const path = require('node:path');
  const root = path.join(__dirname, '..', '..');
  const { TEMPLATES, frameFor } = require('../templates/index.ts');
  const { getPhoto } = require('./manifest.ts');
  const { validatePhotoTokens } = require('../templates/dv-story/photo-tokens.ts');
  const tracks = JSON.parse(fs.readFileSync(path.join(root, 'public/music/sources.json'), 'utf8')).tracks;
  const availableMusic = new Map(tracks.map((track) => [`${track.dir ?? 'music'}/${track.file}`, track]));
  for (const [id, { definition, catalog }] of Object.entries(TEMPLATES)) {
    const fixture = JSON.parse(fs.readFileSync(path.join(root, catalog.package.fixture), 'utf8'));
    assert.equal(fixture.template, id);
    const props = definition.schema.parse({ ...definition.defaultProps, ...fixture.props });
    assert.doesNotThrow(() => frameFor(catalog, props.format), id);
    const checkPhoto = (photoId) => {
      const file = path.join(root, 'public', getPhoto(photoId).file);
      assert.ok(fs.statSync(file).isFile(), `${id}: ${photoId} needs a shipped image`);
      return true;
    };
    for (const [slot, spec] of Object.entries(catalog.slots)) {
      const value = props.photos[slot];
      if (spec.kind === 'tokens') validatePhotoTokens({ [slot]: value }, checkPhoto);
      else for (const photoId of Array.isArray(value) ? value : [value]) checkPhoto(photoId);
    }
    for (const music of [props.music, props.music2]) {
      if (!music?.src) continue;
      const track = availableMusic.get(music.src);
      assert.ok(track, `${id}: ${music.src} needs a declared source`);
      if (track.distribution === 'bundled') {
        assert.ok(fs.statSync(path.join(root, 'public', music.src)).isFile(), `${id}: bundled soundtrack is missing`);
      }
    }
  }
});

test('the default Studio input opens the shipped Doodle wedding fixture', () => {
  const path = require('node:path');
  const root = path.join(__dirname, '..', '..');
  const read = (name) => JSON.parse(fs.readFileSync(path.join(root, name), 'utf8'));
  assert.deepEqual(read('inputs.json'), read('examples/doodle-wedding.json'));
});

test('the example entry registers every wedding template with its metadata calculator', () => {
  const path = require('node:path');
  const { createRequire } = require('node:module');
  const { Children } = require('react');
  const { TEMPLATES } = require('../templates/index.ts');
  const entry = path.join(__dirname, '..', '..', 'examples/cases.tsx');
  const entryRequire = createRequire(entry);
  let Root;
  const { outputText } = ts.transpileModule(fs.readFileSync(entry, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true, jsx: ts.JsxEmit.ReactJSX },
  });
  new Function('require', 'exports', outputText)((id) => id === 'remotion'
    ? { ...entryRequire(id), registerRoot: (component) => { Root = component; } }
    : entryRequire(id), {});
  assert.equal(typeof Root, 'function');
  const compositions = new Map(Children.toArray(Root().props.children).map((element) => [element.props.id, element.props]));
  for (const { definition, catalog } of Object.values(TEMPLATES)) {
    const composition = compositions.get(catalog.compositionId);
    assert.ok(composition, `${catalog.id} needs a reproducible example composition`);
    assert.equal(composition.component, definition.component, catalog.id);
    if (definition.calculateMetadata) {
      assert.equal(composition.calculateMetadata, definition.calculateMetadata, `${catalog.id} needs its timing metadata`);
    }
  }
});

test('schema/<id>.json matches each template\'s zod schema, so vvv.py validate agrees with the renderer', () => {
  const path = require('node:path');
  const exporter = require('../../scripts/export-schemas.cjs');
  const dir = path.join(__dirname, '..', '..', 'schema');
  for (const id of exporter.ids()) {
    assert.equal(fs.readFileSync(path.join(dir, `${id}.json`), 'utf8'), exporter.text(id), `schema/${id}.json is stale; run npm run schemas`);
  }
  assert.deepEqual(fs.readdirSync(dir).sort(), exporter.ids().map((id) => `${id}.json`));
});

test('catalog formats[f].slots and the definition formatSlots name the same slots', () => {
  const { TEMPLATES } = require('../templates/index.ts');
  for (const [id, { definition, catalog }] of Object.entries(TEMPLATES)) {
    const fromCatalog = Object.fromEntries(Object.entries(catalog.formats).filter(([, f]) => f.slots).map(([name, f]) => [name, f.slots]));
    assert.deepEqual(fromCatalog, definition.formatSlots ?? {}, id);
    for (const used of Object.values(fromCatalog)) for (const slot of used) assert.ok(catalog.slots[slot], `${id}: ${slot}`);
  }
});

test('the Album short needs only its opening, gallery and ending; the 16:9 film still needs every slot', () => {
  const { album } = require('../templates/album/index.tsx');
  const fixture = require('../../examples/album-wedding.json').props;
  const { opening, ending, gallery } = fixture.photos;
  const vertical = { ...album.defaultProps, ...fixture, format: '9:16', photos: { ...album.defaultProps.photos, opening, ending, gallery: gallery.slice(0, 3) } };
  assert.equal(album.schema.safeParse(vertical).success, true);
  const noEnding = album.schema.safeParse({ ...vertical, photos: { ...vertical.photos, ending: '' } });
  assert.equal(noEnding.success, false);
  assert.deepEqual(noEnding.error.issues[0].path, ['photos', 'ending']);
  const wide = album.schema.safeParse({ ...vertical, format: '16:9' });
  assert.equal(wide.success, false);
  assert.ok(wide.error.issues.some((issue) => issue.path.join('.') === 'photos.bride'));
  assert.equal(album.schema.safeParse({ ...album.defaultProps, ...fixture }).success, true);
});

test('the Album short ends 8 beats after its last shot, whatever the gallery size', () => {
  const { shortSeconds } = require('../templates/album/short.tsx');
  const { photos } = require('../../examples/album-wedding.json').props;
  const beat = 60 / 84;
  const B = (n) => 2.86 + n * beat;
  // One gallery photo is one shot: 8 opening beats, 4 for the shot, 8 for the closing card.
  assert.ok(Math.abs(shortSeconds({ ...photos, gallery: [photos.gallery[1]] }) - (B(8 + 4 + 8) + 1.2)) < 1e-9);
  const full = shortSeconds(photos);
  const shots = Math.round((full - 1.2 - B(8 + 8)) / (4 * beat));
  assert.ok(shots > 1 && shots <= 12, `${shots} shots`);
  assert.ok(Math.abs(full - (B(8 + shots * 4 + 8) + 1.2)) < 1e-9);
});

test('a template timeline in the catalog matches the pages its code plays', () => {
  const path = require('node:path');
  const root = path.join(__dirname, '..', '..');
  for (const id of ['cinema', 'editorial', 'memoir']) {
    const catalog = JSON.parse(fs.readFileSync(path.join(root, `catalog/${id}.json`), 'utf8'));
    const source = fs.readFileSync(path.join(root, `src/templates/${id}/index.tsx`), 'utf8');
    const pages = [...source.matchAll(/^\s*\["([a-z0-9-]+)", .+, (\d+)\],$/gm)].map((m) => ({ id: m[1], beats: Number(m[2]) }));
    assert.ok(pages.length > 10, id);
    assert.deepEqual(catalog.timeline.pages, pages, id);
    assert.ok(pages.some((p) => p.id === catalog.timeline.climax), id);
    // whole bars, so every page change falls on a downbeat at any pace
    assert.ok(pages.every((p) => p.beats % 4 === 0), id);
  }
});
