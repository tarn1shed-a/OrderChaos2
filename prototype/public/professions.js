// Source player_equipments.Class comments; creation UI is a local adaptation.
export const PROFESSIONS=Object.freeze({1:'战士',2:'法师',3:'游侠',4:'武僧',5:'血骑士'});
export const validProfession=value=>Number.isInteger(value)&&Object.hasOwn(PROFESSIONS,value);
