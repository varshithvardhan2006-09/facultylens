import { Composition } from "remotion";
import { FPS } from "./kit";
import { Promo, promoFrames } from "./Promo";
import { Tech, techFrames } from "./Tech";

export function Root() {
  return (
    <>
      <Composition id="Promo" component={Promo} durationInFrames={promoFrames} fps={FPS} width={1920} height={1080} />
      <Composition id="Tech" component={Tech} durationInFrames={techFrames} fps={FPS} width={1920} height={1080} />
    </>
  );
}
