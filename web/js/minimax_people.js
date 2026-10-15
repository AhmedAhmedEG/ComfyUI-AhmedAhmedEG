/** Boxes are normalized to the original picture, independently of media cropping. */
export function peopleEditor(root, image, settings, save) {
  const container=document.createElement('div');container.className='mmx-people-editor';root.append(container);
  const hint=document.createElement('p');hint.textContent='Draw a box around each person. Drag a box to move it; drag its corner to resize.';container.append(hint);
  const stage=document.createElement('div');stage.className='mmx-people-stage';container.append(stage);stage.append(image);
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 1000 1000');svg.setAttribute('preserveAspectRatio','none');svg.classList.add('mmx-people-boxes');stage.append(svg);
  const rows=document.createElement('div');container.append(rows);settings.boxes ||= [];
  let drag=null;
  const sync=()=>{save();};
  const point=event=>{const r=svg.getBoundingClientRect();return [Math.max(0,Math.min(1,(event.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(event.clientY-r.top)/r.height))];};
  const el=(tag,attrs)=>{const n=document.createElementNS(svg.namespaceURI,tag);for(const [k,v] of Object.entries(attrs))n.setAttribute(k,v);return n;};
  function paint() {
    svg.replaceChildren();rows.replaceChildren();
    settings.boxes.forEach((person,index)=>{
      const [x1,y1,x2,y2]=person.box;
      const rect=el('rect',{x:x1*1000,y:y1*1000,width:(x2-x1)*1000,height:(y2-y1)*1000,'data-index':index,'data-action':'move'});svg.append(rect);
      const text=el('text',{x:x1*1000+8,y:y1*1000+30});text.textContent=String(person.n);svg.append(text);
      svg.append(el('rect',{x:x2*1000-15,y:y2*1000-15,width:30,height:30,'data-index':index,'data-action':'resize',class:'mmx-people-handle'}));
      const row=document.createElement('div');row.className='mmx-person-row';rows.append(row);
      const label=document.createElement('label');label.textContent='Character ';const input=document.createElement('input');input.type='number';input.min=1;input.max=99;input.value=person.n;label.append(input);row.append(label);
      input.onchange=()=>{const number=Number(input.value);if(!Number.isInteger(number)||number<1||number>99||settings.boxes.some((p,i)=>i!==index&&p.n===number)){input.setCustomValidity('Use a distinct number from 1 to 99.');input.reportValidity();input.value=person.n;return;}input.setCustomValidity('');person.n=number;sync();paint();};
      const remove=document.createElement('button');remove.textContent='Remove';remove.onclick=()=>{settings.boxes.splice(index,1);sync();paint();};row.append(remove);
    });
  }
  svg.onpointerdown=event=>{
    if(event.button!==undefined && event.button!==0)return;
    const p=point(event),index=event.target.dataset.index;
    if(index!==undefined)drag={index:Number(index),action:event.target.dataset.action,start:p,original:[...settings.boxes[index].box]};
    else {if(settings.boxes.length>=32)return;let number=1;while(settings.boxes.some(r=>r.n===number))number++;settings.boxes.push({n:number,box:[...p,...p],label:''});drag={index:settings.boxes.length-1,action:'draw',start:p};}
    svg.setPointerCapture?.(event.pointerId);event.preventDefault();paint();
  };
  svg.onpointermove=event=>{
    if(!drag)return;const p=point(event),person=settings.boxes[drag.index];
    if(drag.action==='draw')person.box=[Math.min(p[0],drag.start[0]),Math.min(p[1],drag.start[1]),Math.max(p[0],drag.start[0]),Math.max(p[1],drag.start[1])];
    else if(drag.action==='resize')person.box=[drag.original[0],drag.original[1],Math.max(drag.original[0]+.02,p[0]),Math.max(drag.original[1]+.02,p[1])].map(v=>Math.min(1,v));
    else {const [x1,y1,x2,y2]=drag.original;const dx=Math.max(-x1,Math.min(1-x2,p[0]-drag.start[0])),dy=Math.max(-y1,Math.min(1-y2,p[1]-drag.start[1]));person.box=[x1+dx,y1+dy,x2+dx,y2+dy];}
    paint();
  };
  const finish=()=>{if(!drag)return;const p=settings.boxes[drag.index];if(p.box[2]-p.box[0]<.02||p.box[3]-p.box[1]<.02)settings.boxes.splice(drag.index,1);drag=null;sync();paint();};
  svg.onpointerup=event=>{if(drag)svg.onpointermove(event);finish();};svg.onpointercancel=finish;
  paint();return {refresh:paint};
}
