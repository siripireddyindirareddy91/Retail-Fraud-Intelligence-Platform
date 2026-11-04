import { ResearchDashboard } from './research/Dashboard';
import { Workspace } from './research/Workspace';
import { useEffect, useState } from 'react';
import { api, errorMessage } from './services/api';
import { Link } from 'react-router-dom';
import { ArrowUpRight, ArrowRight, Database, ShieldCheck, Cpu, Beaker, Plus, Download, CircleHelp, Radio, Check, Layers, Terminal, Search } from 'lucide-react';
import { catalog, type Page } from './catalog';

export function EmptyState({title='Ready when you are',description='Run a workflow or adjust your filters to see persisted results.'}:{title?:string;description?:string}){return <div className="empty"><div className="empty-icon"><Layers size={23}/></div><strong>{title}</strong><p>{description}</p></div>}
function Panel({title,tag,children}:{title:string;tag?:string;children:React.ReactNode}){return <section className="panel"><div className="panel-heading"><h2>{title}</h2>{tag&&<span className="muted text-xs">{tag}</span>}</div>{children}</section>}
export function Dashboard(){return <ResearchDashboard/>}
export function Workflow(props:{page:Page;notify:(message:string)=>void}){return <Workspace {...props}/>}

export function PlatformOverview(){return <><PageHeading page={catalog[1]}/><div className="overview-banner"><span className="eyebrow">THE RESEARCH LIFECYCLE</span><h2>From artificial transactions<br/>to measurable model behavior.</h2><p>A connected environment for exploring synthetic augmentation without assuming it improves fraud detection.</p></div><div className="workflow-steps">{[['01','Generate','Create versioned fictional datasets.','/synthetic/generate'],['02','Simulate','Introduce controlled fraud behaviors.','/fraud/scenarios'],['03','Train','Fit models without test leakage.','/models/train'],['04','Evaluate','Compare shared held-out conditions.','/robustness'],['05','Explain','Inspect model feature contributions.','/explainability/shap'],['06','Report','Export results and limitations.','/reports']].map(([n,title,body,url])=><Link key={n} to={url} className="tool-card"><span className="eyebrow">STEP {n}</span><h3>{title}<ArrowRight size={16}/></h3><p>{body}</p></Link>)}</div><div className="notice"><CircleHelp size={19}/><span>Generation, simulation, training, robustness, SHAP and reporting run through authenticated, persisted research jobs.</span></div></>}
export function PageHeading({page}:{page:Page}){return <div className="page-heading"><div><span className="eyebrow">WORKSPACE</span><h1>{page[0]}</h1><p>{page[4]}</p></div></div>}




