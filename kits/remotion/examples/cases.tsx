import React from 'react';
import { Composition, registerRoot } from 'remotion';
import { doodle } from '../src/templates/doodle';
import { album } from '../src/templates/album';
import { dvStory } from '../src/templates/dv-story';
import { comedy } from '../src/templates/comedy';
import { starter } from '../src/templates/starter';
import { editorial } from '../src/templates/editorial';
import { cinema } from '../src/templates/cinema';
import { memoir } from '../src/templates/memoir';
import notebook from './doodle-wedding.json';
import wedding from './album-wedding.json';
import tape from './dv-our-story.json';
import festive from './comedy-wedding.json';
import reel from './starter-reel.json';
import magazine from './editorial-wedding.json';
import screen from './cinema-wedding.json';
import story from './memoir-wedding.json';
import { papercutFrameDemo } from '../src/effects/papercut-frame/demo';
import papercut from './effect-papercut-frame.json';

/** Reproducible fictional cases using the existing MIT demo photographs. */
const Cases: React.FC = () => <>
  <Composition id="VVV-Doodle" component={doodle.component} defaultProps={notebook.props} fps={30} width={1920} height={1080} durationInFrames={4260} />
  <Composition id="VVV-Album" component={album.component} defaultProps={wedding.props} fps={30} width={1920} height={1080} durationInFrames={5925} />
  <Composition id="VVV-Album-Vertical" component={album.component} defaultProps={{ ...wedding.props, format: '9:16' }} fps={30} width={1080} height={1920}
    durationInFrames={Math.ceil(album.seconds({ ...wedding.props, format: '9:16' } as any) * 30)} />
  <Composition id="VVV-DVStory" component={dvStory.component} defaultProps={tape.props} fps={30} width={1920} height={1080} durationInFrames={Math.ceil(dvStory.seconds(tape.props) * 30)} calculateMetadata={dvStory.calculateMetadata} />
  <Composition id="VVV-Comedy" component={comedy.component} defaultProps={festive.props} fps={30} width={1920} height={1080} durationInFrames={Math.ceil(comedy.seconds(festive.props as any) * 30)} />
  <Composition id="VVV-Starter" component={starter.component} defaultProps={reel.props} fps={30} width={1920} height={1080}
    durationInFrames={Math.ceil(starter.seconds(reel.props as any) * 30)} calculateMetadata={starter.calculateMetadata} />
  <Composition id="VVV-Editorial" component={editorial.component} defaultProps={magazine.props} fps={30} width={1920} height={1080}
    durationInFrames={Math.ceil(editorial.seconds(magazine.props as any) * 30)} calculateMetadata={editorial.calculateMetadata} />
  <Composition id="VVV-Cinema" component={cinema.component} defaultProps={screen.props} fps={30} width={1920} height={1080}
    durationInFrames={Math.ceil(cinema.seconds(screen.props as any) * 30)} calculateMetadata={cinema.calculateMetadata} />
  <Composition id="VVV-Memoir" component={memoir.component} defaultProps={story.props} fps={30} width={1920} height={1080}
    durationInFrames={Math.ceil(memoir.seconds(story.props as any) * 30)} calculateMetadata={memoir.calculateMetadata} />
  <Composition id="VVV-Effect-PapercutFrame" component={papercutFrameDemo.component} defaultProps={papercut.props as any} fps={30} width={1920} height={1080}
    durationInFrames={Math.ceil(papercutFrameDemo.seconds(papercut.props as any) * 30)} />
</>;
registerRoot(Cases);
