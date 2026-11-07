import test from 'node:test';
import assert from 'node:assert/strict';
import {projectMinimapPoint,minimapMarkers} from '../public/minimap.js';

test('north-up minimap projects server coordinates relative to its moving player center',()=>{
  const options={size:160,span:480},center={x:900,y:360};
  assert.deepEqual(projectMinimapPoint(center,center,options),{x:80,y:80,edge:false});
  assert.deepEqual(projectMinimapPoint({x:960,y:300},center,options),{x:100,y:60,edge:false});
  assert.deepEqual(projectMinimapPoint({x:960,y:300},{x:930,y:390},options),{x:90,y:50,edge:false});
  const edge=projectMinimapPoint({x:1900,y:1360},center,options);
  assert.equal(edge.edge,true);assert(Math.abs(Math.hypot(edge.x-80,edge.y-80)-68)<1e-9);
  assert.equal(projectMinimapPoint({x:NaN,y:0},center),null);
});

test('map uses each server identity, tracks teammates, removes dead monsters and clears after disconnect',()=>{
  const players=[{id:'a',name:'甲',x:900,y:360,hp:100},{id:'b',name:'乙',x:960,y:360,hp:0}];
  const monsters=[{id:'wolf',name:'狼',x:900,y:300,hp:60,alive:true},{id:'dead',x:910,y:310,hp:0,alive:false}];
  const fromA=minimapMarkers(players,monsters,'a'),fromB=minimapMarkers(players,monsters,'b');
  assert.deepEqual(fromA.map(point=>[point.id,point.kind]),[['a','self'],['b','party'],['wolf','enemy']]);
  assert.equal(fromA[1].dead,true);assert.equal(fromA[1].x,100);
  assert.equal(fromB[1].x,80);assert.equal(fromB[0].x,60);
  assert.deepEqual(minimapMarkers(players,monsters,'missing'),[]);
  assert.deepEqual(minimapMarkers([],[],'a'),[]);
});
