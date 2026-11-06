import { BLOOM_WEIGHTS } from './scene-environment.js';

// Independent implementation of the recovered four-tap bloom extraction,
// separable seven-tap blur, luminance Reinhardt and 512x16 LUT lookup.
export function createRecoveredHDR(THREE,renderer,profile,lut) {
  const hdr=profile.hdr,sceneTarget=new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType,depthBuffer:true});
  const targets=[sceneTarget,...[0,1].map(()=>new THREE.WebGLRenderTarget(1,1,{type:THREE.HalfFloatType,depthBuffer:false}))];
  const geometry=new THREE.PlaneGeometry(2,2),camera=new THREE.OrthographicCamera(-1,1,1,-1,0,1),quadScene=new THREE.Scene();
  const vertex='varying vec2 sampleUV;void main(){sampleUV=uv;gl_Position=vec4(position.xy,0.0,1.0);}';
  function material(uniforms,fragment){return new THREE.ShaderMaterial({uniforms,vertexShader:vertex,fragmentShader:`varying vec2 sampleUV;${fragment}`,depthTest:false,depthWrite:false,toneMapped:false});}
  const extract=material({picture:{value:sceneTarget.texture},pixel:{value:new THREE.Vector2()},scale:{value:hdr.scale},threshold:{value:1},intensity:{value:1}},`
    uniform sampler2D picture;uniform vec2 pixel;uniform float scale;uniform float threshold;uniform float intensity;
    void main(){vec3 total=texture2D(picture,sampleUV).rgb+texture2D(picture,sampleUV+pixel*vec2(-.5,-.5)).rgb;
      total+=texture2D(picture,sampleUV+pixel*vec2(.5,-.5)).rgb+texture2D(picture,sampleUV+pixel*vec2(-.5,.5)).rgb;
      gl_FragColor=vec4(max(total*(scale*.25)-threshold,vec3(0.0))*intensity,1.0);}`);
  const blur=material({picture:{value:targets[1].texture},delta:{value:new THREE.Vector2()}},`
    uniform sampler2D picture;uniform vec2 delta;void main(){vec3 color=vec3(0.0);
    ${BLOOM_WEIGHTS.map((w,i)=>`color+=texture2D(picture,sampleUV+delta*${(i-3).toFixed(1)}).rgb*${w};`).join('\n')}
    gl_FragColor=vec4(color,1.0);}`);
  lut.colorSpace=THREE.NoColorSpace;lut.flipY=false;lut.generateMipmaps=false;lut.minFilter=lut.magFilter=THREE.LinearFilter;lut.needsUpdate=true;
  const tone=material({picture:{value:sceneTarget.texture},bloom:{value:targets[1].texture},lookup:{value:lut},exposure:{value:hdr.exposure},whitePoint:{value:hdr.whitePoint},brightness:{value:hdr.brightness},contrast:{value:hdr.contrast}},`
    uniform sampler2D picture;uniform sampler2D bloom;uniform sampler2D lookup;uniform float exposure;uniform float whitePoint;uniform float brightness;uniform float contrast;
    void main(){vec3 h=pow(max(texture2D(picture,sampleUV).rgb,vec3(0.0)),vec3(2.2))*exposure;
      float mid=whitePoint*.5;h=max((h-mid)*(1.0+.05*(contrast-1.0))+mid+.05*brightness,vec3(0.0));
      float l=dot(h,vec3(.2126,.7152,.0722));float factor=(1.0+l/(whitePoint*whitePoint))/(1.0+l);
      vec3 color=pow(max(clamp(h*factor,0.0,1.0)+texture2D(bloom,sampleUV).rgb,vec3(0.0)),vec3(1.0/2.2));color=clamp(color,0.0,1.0);
      vec2 at=vec2((color.r*14.0+.5+floor(color.b*31.0+.5)*16.0)/512.0,(color.g*15.0+.5)/16.0);
      gl_FragColor=vec4(texture2D(lookup,at).rgb,1.0);}`);
  const quad=new THREE.Mesh(geometry,extract);quad.frustumCulled=false;quadScene.add(quad);
  let width=1,height=1,bloomW=1,bloomH=1,disposed=false;
  renderer.toneMapping=THREE.NoToneMapping;renderer.toneMappingExposure=1;
  const pass=(mat,target)=>{quad.material=mat;renderer.setRenderTarget(target);renderer.render(quadScene,camera);};
  return {
    setSize(w,h){if(w===width&&h===height)return;width=w;height=h;bloomW=Math.max(1,Math.floor(w*hdr.downscale));bloomH=Math.max(1,Math.floor(h*hdr.downscale));
      sceneTarget.setSize(w,h);targets[1].setSize(bloomW,bloomH);targets[2].setSize(bloomW,bloomH);extract.uniforms.pixel.value.set(1/w,1/h);},
    render(scene,viewCamera,zone){if(disposed)return;const previous=renderer.getRenderTarget();
      extract.uniforms.threshold.value=Math.min(1,zone.bloom.decrease+hdr.thresholdOffset);extract.uniforms.intensity.value=Math.min(1,zone.bloom.intensity);
      renderer.setRenderTarget(sceneTarget);renderer.render(scene,viewCamera);pass(extract,targets[1]);
      for(let i=1;i<=hdr.blurIterations;i++){
        blur.uniforms.picture.value=targets[1].texture;blur.uniforms.delta.value.set(i*hdr.blurWidth/bloomW,0);pass(blur,targets[2]);
        blur.uniforms.picture.value=targets[2].texture;blur.uniforms.delta.value.set(0,i*hdr.blurWidth/bloomH);pass(blur,targets[1]);
      }
      pass(tone,previous);
    },
    state:()=>({width,height,bloomW,bloomH,passes:3+hdr.blurIterations*2,precision:'half-float'}),
    dispose(){if(disposed)return;disposed=true;for(const target of targets)target.dispose();for(const mat of[extract,blur,tone])mat.dispose();geometry.dispose();},
  };
}
