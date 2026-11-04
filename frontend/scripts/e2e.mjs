import { spawn, spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const frontend=fileURLToPath(new URL('../',import.meta.url));
const backend=resolve(frontend,'../backend');
const apiPort=Number(process.env.RF_E2E_API_PORT||8001);
const frontendPort=Number(process.env.RF_E2E_FRONTEND_PORT||5175);
if(![apiPort,frontendPort].every(port=>Number.isInteger(port)&&port>=1024&&port<=65535)||apiPort===frontendPort)throw new Error('Browser-test ports must be distinct ports between 1024 and 65535');
const apiURL=`http://127.0.0.1:${apiPort}`;
const frontendURL=`http://127.0.0.1:${frontendPort}`;
const owned=[];
function launch(command,args,options={}){const child=spawn(command,args,{cwd:frontend,stdio:'inherit',windowsHide:true,...options});child.on('error',error=>{child.startupError=error});owned.push(child);return child;}
const startupTimeout=Number(process.env.RF_E2E_STARTUP_TIMEOUT_MS||180000);
if(!Number.isFinite(startupTimeout)||startupTimeout<1000||startupTimeout>600000)throw new Error('RF_E2E_STARTUP_TIMEOUT_MS must be between 1000 and 600000');
async function ready(url,child){const deadline=Date.now()+startupTimeout;let status='no response';while(Date.now()<deadline){if(child.startupError)throw new Error(`Test server could not launch: ${child.startupError.code}`);if(child.exitCode!==null||child.signalCode!==null)throw new Error(`Test server exited before becoming ready (${child.exitCode??child.signalCode}): ${url}`);try{const response=await fetch(url,{signal:AbortSignal.timeout(5000)});if(response.ok)return;status=`HTTP ${response.status}`}catch{}await new Promise(r=>setTimeout(r,400));}throw new Error(`Test server did not become ready within ${startupTimeout}ms (${status}): ${url}`);}
function stop(){for(const child of owned.reverse()){if(!child.pid||child.exitCode!==null||child.signalCode!==null)continue;if(process.platform==='win32')spawnSync(resolve(process.env.SystemRoot||'C:/Windows','System32/taskkill.exe'),['/PID',String(child.pid),'/T','/F'],{windowsHide:true,stdio:'ignore',timeout:10000});else child.kill('SIGTERM');}}
let code=1;
try{
 const external=process.env.PLAYWRIGHT_BASE_URL;
 if(!external){
  // Fail if the dedicated test ports are already in use; never kill an unrelated server.
  for(const url of [`${apiURL}/api/v1/health/live`,frontendURL]){let inUse=false;try{await fetch(url,{signal:AbortSignal.timeout(500)});inUse=true}catch{}if(inUse)throw new Error(`Dedicated test port is already in use: ${url}`);}
  const api=launch(resolve(backend,process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python'),['-m','app.e2e_server'],{cwd:backend});
  await ready(`${apiURL}/api/v1/health/ready`,api);
  const vite=launch(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(frontendPort),'--strictPort'],{env:{...process.env,RF_API_PROXY:apiURL}});
  await ready(frontendURL,vite);
 }
 const runner=launch(process.execPath,['node_modules/@playwright/test/cli.js','test',...process.argv.slice(2)],{env:{...process.env,RF_E2E_EXTERNAL:'1',PLAYWRIGHT_BASE_URL:external||frontendURL}});
 code=await new Promise((resolve,reject)=>{runner.on('error',reject);runner.on('exit',value=>resolve(value??1))});
}catch(error){console.error(error.message)}finally{stop()}
process.exitCode=code;


