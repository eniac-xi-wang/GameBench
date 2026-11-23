// Headless frontend for the unmodified ccleste engine. One update + draw per tick.
#include <algorithm>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <vector>
#define CELESTE_P8_FIXEDP
#include "../../celeste-classic/celeste.c"
#undef float
#undef this
#undef bool
#undef true
#undef false
#include "../../celeste-classic/tilemap.h"

static unsigned char pixels[128*128], gfxdata[128*64], fontdata[128*128];
static int palette[16], camera_x=0, camera_y=0, input_mask=0;
static void put(int x,int y,int c) {
    x-=camera_x; y-=camera_y;
    if (x>=0&&x<128&&y>=0&&y<128) pixels[y*128+x]=palette[c&15];
}
static void rect(int x,int y,int x1,int y1,int c) {
    for(int j=std::max(y,camera_y);j<=std::min(y1,camera_y+127);j++)
        for(int i=std::max(x,camera_x);i<=std::min(x1,camera_x+127);i++) put(i,j,c);
}
static void blit(const unsigned char* data,int height,int sx,int sy,int w,int h,int x,int y,int fx,int fy,int color=-1) {
    for(int j=0;j<h;j++) for(int i=0;i<w;i++) {
        int a=sx+(fx?w-1-i:i),b=sy+(fy?h-1-j:j);
        if(a<0||a>=128||b<0||b>=height) continue;
        int c=data[b*128+a]; if(c) put(x+i,y+j,color<0?c:color);
    }
}
static int tile(int x,int y) {
    int i=x+y*128;
    return x>=0&&x<128&&y>=0&&i<(int)(sizeof(tilemap_data)/sizeof(*tilemap_data))?tilemap_data[i]:0;
}
static int flag(int t,int f) { return t>=0&&t<(int)(sizeof(tile_flags)/sizeof(*tile_flags))&&f>=0&&f<8 ? (tile_flags[t]>>f)&1 : 0; }
static int callback(CELESTE_P8_CALLBACK_TYPE call,...) {
    va_list a; va_start(a,call); int out=0;
    #define ARG va_arg(a,int)
    switch(call) {
    case CELESTE_P8_BTN: {int b=ARG;out=(input_mask>>b)&1;break;}
    case CELESTE_P8_MGET: {int x=ARG,y=ARG;out=tile(x,y);break;}
    case CELESTE_P8_FGET: {int t=ARG,f=ARG;out=flag(t,f);break;}
    case CELESTE_P8_CAMERA: {camera_x=ARG;camera_y=ARG;break;}
    case CELESTE_P8_PAL_RESET: {for(int i=0;i<16;i++)palette[i]=i;break;}
    case CELESTE_P8_PAL: {int x=ARG,y=ARG;palette[x&15]=y&15;break;}
    case CELESTE_P8_RECTFILL: {int x=ARG,y=ARG,x1=ARG,y1=ARG,c=ARG;rect(x,y,x1,y1,c);break;}
    case CELESTE_P8_LINE: {
        int x=ARG,y=ARG,x1=ARG,y1=ARG,c=ARG;
        x=std::clamp(x,camera_x,camera_x+127);y=std::clamp(y,camera_y,camera_y+127);
        x1=std::clamp(x1,camera_x,camera_x+127);y1=std::clamp(y1,camera_y,camera_y+127);
        int dx=abs(x1-x),sx=x<x1?1:-1,dy=-abs(y1-y),sy=y<y1?1:-1,e=dx+dy;
        while(x!=x1||y!=y1){put(x,y,c);int e2=2*e;if(e2>=dy){e+=dy;x+=sx;}if(e2<=dx){e+=dx;y+=sy;}}break;
    }
    case CELESTE_P8_CIRCFILL: {
        int x=ARG,y=ARG,r=ARG,c=ARG;
        if(r<=1){rect(x-1,y,x+1,y,c);rect(x,y-1,x,y+1,c);}
        else if(r==2){rect(x-2,y-1,x+2,y+1,c);rect(x-1,y-2,x+1,y+2,c);}
        else if(r==3){rect(x-3,y-1,x+3,y+1,c);rect(x-1,y-3,x+1,y+3,c);rect(x-2,y-2,x+2,y+2,c);}
        else for(int j=-r;j<=r;j++)for(int i=-r;i<=r;i++)if(i*i+j*j<=r*r)put(x+i,y+j,c);
        break;
    }
    case CELESTE_P8_SPR: {
        int s=ARG,x=ARG,y=ARG,w=ARG,h=ARG,fx=ARG,fy=ARG;
        blit(gfxdata,64,(s%16)*8,(s/16)*8,w*8,h*8,x,y,fx,fy);break;
    }
    case CELESTE_P8_PRINT: {
        const char* s=va_arg(a,const char*);int x=ARG,y=ARG,c=ARG;
        for(;*s;s++,x+=4){int ch=*s&127;blit(fontdata,128,(ch%16)*8,(ch/16)*8,8,8,x,y,0,0,c);}break;
    }
    case CELESTE_P8_MAP: {
        int mx=ARG,my=ARG,tx=ARG,ty=ARG,w=ARG,h=ARG,m=ARG;
        for(int x=0;x<w;x++)for(int y=0;y<h;y++){
            int t=tile(mx+x,my+y);
            if(m==0||(m==4&&tile_flags[t]==4)||flag(t,m!=4?m-1:m))
                blit(gfxdata,64,(t%16)*8,(t/16)*8,8,8,tx+x*8,ty+y*8,0,0);
        }break;
    }
    default: break; // Audio has no feedback into physics.
    }
    #undef ARG
    va_end(a);return out;
}
static void bmp(const std::string& path,unsigned char* dest,int capacity) {
    std::ifstream f(path,std::ios::binary);std::vector<unsigned char> b((std::istreambuf_iterator<char>(f)),{});
    auto u32=[&](int p){return uint32_t(b.at(p))|(uint32_t(b.at(p+1))<<8)|(uint32_t(b.at(p+2))<<16)|(uint32_t(b.at(p+3))<<24);};
    int off=u32(10),w=u32(18),h=u32(22),bits=b.at(28),stride=((w*bits+31)/32)*4;
    if(w!=128||h<1||h*128>capacity||(bits!=1&&bits!=4))throw std::runtime_error("unsupported asset BMP");
    for(int y=0;y<h;y++)for(int x=0;x<w;x++)dest[y*w+x]=(b.at(off+(h-y-1)*stride+x*bits/8)>>(8-bits-(x*bits%8)))&((1<<bits)-1);
}
static OBJ* player() {for(auto& o:objects)if(o.active&&o.type==OBJ_PLAYER)return &o;return nullptr;}
static void tick(int mask){input_mask=mask;Celeste_P8_update();Celeste_P8_draw();}
static void record(std::ofstream& trace,std::ofstream& video,int f,int mask) {
    trace<<"{\"frame\":"<<f<<",\"input\":"<<mask<<",\"room\":"<<level_index()<<",\"deaths\":"<<deaths<<",\"freeze\":"<<freeze<<",\"player\":";
    auto p=player();
    if(p)trace<<"{\"x\":"<<double(p->x)<<",\"y\":"<<double(p->y)<<",\"vx\":"<<double(p->spd.x)<<",\"vy\":"<<double(p->spd.y)<<",\"dash\":"<<p->djump<<",\"ground\":"<<(OBJ_is_solid(p,0,1)?"true":"false")<<"}";
    else trace<<"null";
    trace<<"}\n";video.write((char*)pixels,sizeof(pixels));
}
int main(int argc,char** argv) {
    try {
        if(argc!=4)throw std::runtime_error("usage: runner ASSETS INPUT_MASKS OUTPUT_DIR");
        bmp(std::string(argv[1])+"/gfx.bmp",gfxdata,sizeof(gfxdata));
        bmp(std::string(argv[1])+"/font.bmp",fontdata,sizeof(fontdata));
        for(int i=0;i<16;i++)palette[i]=i;
        Celeste_P8_set_call_func(callback);Celeste_P8_set_rndseed(8);Celeste_P8_init();
        // Canonical noninteractive title/start prefix, then zero-input spawn.
        tick(16);int warmup=1;
        while(!player()&&warmup<300){tick(0);warmup++;}
        if(!player()||level_index()!=0)throw std::runtime_error("canonical start failed");
        std::ifstream in(argv[2]);if(!in)throw std::runtime_error("input missing");
        std::ofstream tr(std::string(argv[3])+"/trace.jsonl"),vid(std::string(argv[3])+"/frames.bin",std::ios::binary);
        if(!tr||!vid)throw std::runtime_error("output unavailable");
        tr.precision(10);record(tr,vid,0,0);int mask,n=0;
        while(in>>mask){if(mask<0||mask>63||n>=600)throw std::runtime_error("invalid input");tick(mask);record(tr,vid,++n,mask);if(level_index()!=0)break;}
        std::cout<<"{\"success\":"<<(level_index()==1?"true":"false")<<",\"frames\":"<<n<<",\"deaths\":"<<deaths<<",\"warmup_frames\":"<<warmup<<",\"end_room\":"<<level_index()<<"}\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
