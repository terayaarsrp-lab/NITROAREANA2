// Usage: node tools/carinfo.js cars/blade.car  -- prints wheel geometry checks
const fs=require('fs');
function load(f){const b=fs.readFileSync(f);const buf=b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);const dv=new DataView(buf);
  const jl=dv.getUint32(4,true),hdr=JSON.parse(new TextDecoder().decode(new Uint8Array(buf,8,jl)));return{buf,hdr,base:8+jl}}
function pos(c,p){const q=new Int16Array(c.buf,c.base+p.pos,p.v*3),o=new Float32Array(p.v*3);for(let i=0;i<p.v;i++)for(let k=0;k<3;k++)o[i*3+k]=p.pmin[k]+(q[i*3+k]+32768)/65535*p.prng[k];return o}
module.exports={load,pos};
if(require.main===module)for(const f of process.argv.slice(2)){const c=load(f),H=c.hdr;
  console.log('==',f,'L',H.L,'W',H.W,'H',H.H);
  H.wheels.forEach((w,k)=>{let mn=[1e9,1e9,1e9],mx=[-1e9,-1e9,-1e9],n=0,rs=[];
    for(const p of H.parts.hi){if(p.wheel!==k)continue;const P=pos(c,p);for(let i=0;i<p.v;i++){for(let a=0;a<3;a++){mn[a]=Math.min(mn[a],P[i*3+a]);mx[a]=Math.max(mx[a],P[i*3+a])}rs.push(Math.hypot(P[i*3+1],P[i*3+2]));n++}}
    rs.sort((a,b)=>a-b);const r95=rs[Math.floor(rs.length*.97)];
    console.log(` w${k} ${w.front?'F':'R'} pivot(${w.x.toFixed(2)},${w.y.toFixed(2)},${w.z.toFixed(2)}) r=${w.r.toFixed(2)} | y[${mn[1].toFixed(2)},${mx[1].toFixed(2)}] z[${mn[2].toFixed(2)},${mx[2].toFixed(2)}] x[${mn[0].toFixed(2)},${mx[0].toFixed(2)}] r97=${r95.toFixed(2)} n=${n}`)})}
