// Deployment recovery only. Never replace original physics or award/move a role.
export function isPhysicsTransportFailure(error){
  return error instanceof Error &&
    (error.message==='原碰撞执行超时；没有切换到替代算法'||
     /^Original physics worker exited \(/.test(error.message));
}

export function createRuntimeRecovery({close,exit,report=console.error}){
  let pending=null;
  return {
    fail(error){
      if(!isPhysicsTransportFailure(error)||pending)return false;
      // Let the failed handler unwind. close() stops ticks, flushes the last
      // accepted state, closes sockets, then shuts down the original worker.
      pending=Promise.resolve().then(close).then(()=>exit(1),failure=>{
        report('运行服务关闭失败：'+failure.message);exit(1);
      });
      return true;
    },
    get completion(){return pending||Promise.resolve();}
  };
}
