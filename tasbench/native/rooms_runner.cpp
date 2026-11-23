// Additional room tasks share the untouched legacy renderer and engine frontend.
#define main legacy_runner_main
#include "runner.cpp"
#undef main
#include <sstream>
#include <sys/wait.h>
#include <unistd.h>

static std::vector<int> read_inputs(const std::string& path, int limit=10000) {
    std::ifstream f(path); if(!f) throw std::runtime_error("input file missing");
    std::vector<int> v; int n;
    while(f>>n) {if(n<0||n>63||(int)v.size()>=limit)throw std::runtime_error("invalid input sequence");v.push_back(n);}
    if(!f.eof())throw std::runtime_error("invalid input text");
    return v;
}
static int canonical(const std::string& assets) {
    bmp(assets+"/gfx.bmp",gfxdata,sizeof(gfxdata));bmp(assets+"/font.bmp",fontdata,sizeof(fontdata));
    for(int i=0;i<16;i++)palette[i]=i;
    Celeste_P8_set_call_func(callback);Celeste_P8_set_rndseed(8);Celeste_P8_init();
    tick(16);int warmup=1;
    while(!player()&&warmup<300){tick(0);warmup++;}
    if(!player()||level_index()!=0)throw std::runtime_error("canonical start failed");
    return warmup;
}
static void result(int target,int n,int warmup,int prefix) {
    std::cout<<"{\"success\":"<<(level_index()==target+1?"true":"false")
             <<",\"frames\":"<<n<<",\"deaths\":"<<deaths<<",\"warmup_frames\":"<<warmup+prefix
             <<",\"prefix_frames\":"<<prefix<<",\"start_room\":"<<target<<",\"end_room\":"<<level_index()<<"}\n";
}
int main(int argc,char** argv) {
    try {
        if(argc<2)throw std::runtime_error("expected --scan or --run");
        std::string mode=argv[1];
        if(mode=="--scan") {
            if(argc!=5)throw std::runtime_error("--scan ASSETS INPUTS TRACE");
            canonical(argv[2]);auto inputs=read_inputs(argv[3]);
            std::ofstream tr(argv[4]),vid("/dev/null",std::ios::binary);
            tr.precision(10);record(tr,vid,0,0);
            int n=0;for(int mask:inputs){tick(mask);record(tr,vid,++n,mask);}
            std::cout<<"{\"frames\":"<<n<<",\"end_room\":"<<level_index()<<",\"deaths\":"<<deaths<<"}\n";
        } else if(mode=="--batch") {
            if(argc!=5)throw std::runtime_error("--batch ASSETS PREFIX ROOM");
            int target=std::stoi(argv[4]);if(target<0||target>=30)throw std::runtime_error("invalid room");
            int warmup=canonical(argv[2]);auto prefix=read_inputs(argv[3]);for(int mask:prefix)tick(mask);
            if(level_index()!=target||!player())throw std::runtime_error("invalid trusted prefix");
            // Fork from this immutable start: includes engine, renderer and function-static IDs.
            // The engine's save_state omits init_object's static counter, so it is not used here.
            std::string line;
            while(std::getline(std::cin,line)) {
                std::istringstream in(line);std::vector<int> inputs;int mask;
                while(in>>mask){if(mask<0||mask>63||inputs.size()>=600)throw std::runtime_error("invalid input");inputs.push_back(mask);}
                if(!in.eof()||inputs.empty())throw std::runtime_error("invalid input line");
                std::cout.flush();pid_t child=fork();if(child<0)throw std::runtime_error("fork failed");
                if(child==0){int n=0;for(int m:inputs){tick(m);++n;if(level_index()!=target)break;}result(target,n,warmup,prefix.size());std::cout.flush();_exit(0);}
                int status=0;if(waitpid(child,&status,0)!=child||!WIFEXITED(status)||WEXITSTATUS(status)!=0)throw std::runtime_error("batch trial failed");
            }
        } else if(mode=="--run") {
            if(argc!=7)throw std::runtime_error("--run ASSETS PREFIX INPUTS OUTPUT_DIR ROOM");
            int target=std::stoi(argv[6]);if(target<0||target>=30)throw std::runtime_error("invalid room");
            int warmup=canonical(argv[2]);auto prefix=read_inputs(argv[3]);for(int mask:prefix)tick(mask);
            if(level_index()!=target||!player())throw std::runtime_error("trusted prefix did not reach the declared starting room/player");
            auto inputs=read_inputs(argv[4],600);
            std::ofstream tr(std::string(argv[5])+"/trace.jsonl"),vid(std::string(argv[5])+"/frames.bin",std::ios::binary);
            if(!tr||!vid)throw std::runtime_error("output unavailable");
            tr.precision(10);record(tr,vid,0,0);int n=0;
            for(int mask:inputs){tick(mask);record(tr,vid,++n,mask);if(level_index()!=target)break;}
            result(target,n,warmup,prefix.size());
        } else throw std::runtime_error("unknown mode");
    } catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}
