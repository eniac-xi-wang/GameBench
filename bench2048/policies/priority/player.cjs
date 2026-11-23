'use strict';
exports.chooseAction=o=>[0,1,2,3].find(a=>o.legal_actions.includes(a));
