/** @typedef {{key:string,label:string,type:'string'|'int'|'number'|'date'|'select'|'bool',required?:boolean,min?:number,max?:number,default?:unknown,options?:string[],help?:string}} Field */
/** @typedef {{key:string,label:string}} AnalysisKind */
/** @typedef {{title:string,short_name:string,subtitle:string,organization:string,workflow:string,pages:string[],fields:Field[],params:Field[],methodology:string[],kinds:AnalysisKind[],effect_params:Field[],effect_methodology:string[],completion_fields:Field[],completion_sample:string}} ProjectSpec */
export {};
