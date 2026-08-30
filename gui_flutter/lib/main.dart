import 'dart:io';
import 'package:flutter/material.dart';

void main() => runApp(const DanaApp());

class DanaApp extends StatelessWidget {
  const DanaApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    debugShowCheckedModeBanner: false,
    title: 'Dana',
    theme: ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: const Color(0xFF0B1020),
      colorScheme: const ColorScheme.dark(primary: Color(0xFF5B8CFF), surface: Color(0xFF121A2C)),
      fontFamily: 'Inter',
    ),
    home: const DanaHome(),
  );
}

class DanaHome extends StatefulWidget { const DanaHome({super.key}); @override State<DanaHome> createState()=>_DanaHomeState(); }
class _DanaHomeState extends State<DanaHome> {
  int page=0; bool running=false; int workers=5; String port='8765'; String mode='Tailscale Funnel'; String url='Not running';
  final paths=TextEditingController(); final logs=TextEditingController(); Process? server;
  final names=['Overview','Connection','Access','Analytics','Tools','Logs'];
  final icons=[Icons.grid_view_rounded,Icons.link_rounded,Icons.folder_shared_rounded,Icons.query_stats_rounded,Icons.extension_rounded,Icons.terminal_rounded];
  @override void dispose(){paths.dispose();logs.dispose();server?.kill();super.dispose();}
  Future<void> startDana() async {
    if(running)return;
    try {
      final exe=Platform.environment['DANA_PYTHON'] ?? (Platform.isWindows ? '.venv\\Scripts\\python.exe' : '.venv/bin/python');
      server=await Process.start(exe,['-m','dana.main'],workingDirectory:Directory.current.path,environment:{...Platform.environment,'DANA_PORT':port,'DANA_WORKERS':'$workers'});
      server!.stdout.transform(systemEncoding.decoder).listen((v){logs.text+=v;setState((){});});
      server!.stderr.transform(systemEncoding.decoder).listen((v){logs.text+=v;setState((){});});
      setState((){running=true;url='http://127.0.0.1:$port/mcp';});
    } catch(e){logs.text+='Start error: $e\n';setState((){});}
  }
  void stopDana(){server?.kill();setState((){running=false;url='Not running';});}
  @override Widget build(BuildContext context){
    final body=[overview(),connection(),access(),analytics(),tools(),logPage()][page];
    return Scaffold(body: SafeArea(child: Row(children:[sidebar(),Expanded(child: body)])));
  }
  Widget sidebar()=>Container(width:250,margin:const EdgeInsets.all(16),padding:const EdgeInsets.all(14),decoration:BoxDecoration(color:const Color(0xFF10182A),borderRadius:BorderRadius.circular(28),border:Border.all(color:Colors.white10)),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[
    const Padding(padding:EdgeInsets.all(10),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text('DANA',style:TextStyle(fontSize:26,fontWeight:FontWeight.w800,letterSpacing:2)),SizedBox(height:4),Text('MCP CONTROL CENTER',style:TextStyle(color:Colors.white54,fontSize:10,letterSpacing:1.5))])),const SizedBox(height:22),
    for(int i=0;i<names.length;i++) Padding(padding:const EdgeInsets.only(bottom:6),child:ListTile(leading:Icon(icons[i]),title:Text(names[i]),selected:page==i,shape:RoundedRectangleBorder(borderRadius:BorderRadius.circular(16)),onTap:()=>setState(()=>page=i))),
    const Spacer(),Container(padding:const EdgeInsets.all(14),decoration:BoxDecoration(color:const Color(0xFF0B1020),borderRadius:BorderRadius.circular(18)),child:Row(children:[Container(width:9,height:9,decoration:BoxDecoration(color:running?Colors.greenAccent:Colors.white38,shape:BoxShape.circle)),const SizedBox(width:10),Text(running?'Dana is running':'Dana is offline')]))]));
  Widget shell(String title,String subtitle,List<Widget> children)=>Padding(padding:const EdgeInsets.fromLTRB(34,28,34,28),child:Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Text(title,style:const TextStyle(fontSize:32,fontWeight:FontWeight.w800)),const SizedBox(height:6),Text(subtitle,style:const TextStyle(color:Colors.white54)),const SizedBox(height:28),...children]));
  Widget overview()=>shell('Overview','Everything important, without the noise.',[
    Wrap(spacing:14,runSpacing:14,children:[stat('Status',running?'Online':'Offline',running?Icons.check_circle:Icons.pause_circle),stat('Workers','$workers',Icons.hub_rounded),stat('Mode',mode,Icons.public_rounded),stat('Endpoint',running?'/mcp':'—',Icons.bolt_rounded)]),const SizedBox(height:24),card(Column(crossAxisAlignment:CrossAxisAlignment.start,children:[const Text('Connection URL',style:TextStyle(color:Colors.white54)),const SizedBox(height:8),SelectableText(url,style:const TextStyle(fontSize:18,fontWeight:FontWeight.w700)),const SizedBox(height:16),Row(children:[FilledButton.icon(onPressed:running?null:startDana,icon:const Icon(Icons.play_arrow),label:const Text('Start Dana')),const SizedBox(width:10),OutlinedButton.icon(onPressed:running?stopDana:null,icon:const Icon(Icons.stop),label:const Text('Stop'))])]))]);
  Widget connection()=>shell('Connection','Configure the local service and public exposure.',[card(Column(crossAxisAlignment:CrossAxisAlignment.start,children:[TextField(controller:TextEditingController(text:port),keyboardType:TextInputType.number,decoration:const InputDecoration(labelText:'Backend port')),const SizedBox(height:16),DropdownButtonFormField<String>(initialValue:mode,items:['Tailscale Funnel','Local only'].map((x)=>DropdownMenuItem(value:x,child:Text(x))).toList(),onChanged:(x)=>setState(()=>mode=x!),decoration:const InputDecoration(labelText:'Exposure')),const SizedBox(height:20),Row(children:[const Text('Workers'),const Spacer(),IconButton(onPressed:workers>1?()=>setState(()=>workers--):null,icon:const Icon(Icons.remove)),Text('$workers'),IconButton(onPressed:workers<128?()=>setState(()=>workers++):null,icon:const Icon(Icons.add))])]))]);
  Widget access()=>shell('Access control','Only listed paths are allowed. Leave empty for unrestricted access.',[Expanded(child:card(TextField(controller:paths,maxLines:null,expands:true,decoration:const InputDecoration(border:InputBorder.none,hintText:'/home/user/project\nC:\\Projects\\Dana'))))]);
  Widget analytics()=>shell('Analytics','Token and execution timing are collected by Dana.',[Wrap(spacing:14,runSpacing:14,children:[stat('Total tokens','Live via Dana',Icons.token),stat('Operations','Live via Dana',Icons.functions),stat('Operation time','Live via Dana',Icons.timer_outlined),stat('Session time','Live via Dana',Icons.schedule)])]);
  Widget tools()=>shell('Tools','Capabilities currently available in Dana.',[Expanded(child:card(ListView(children:const [
    ListTile(leading:Icon(Icons.memory),title:Text('Codebase memory & context optimization'),subtitle:Text('Indexing, symbols, dependencies, delta context and deduplication')),
    ListTile(leading:Icon(Icons.analytics_outlined),title:Text('Token & time analytics'),subtitle:Text('Per-operation, session and all-time statistics')),
    ListTile(leading:Icon(Icons.folder_copy_outlined),title:Text('Filesystem & access policy')),
    ListTile(leading:Icon(Icons.code),title:Text('Formatting, testing, debugging & documentation')),
    ListTile(leading:Icon(Icons.picture_as_pdf_outlined),title:Text('PDF & Word with Persian/RTL support')),
    ListTile(leading:Icon(Icons.language),title:Text('Web and browser capabilities')),
  ])))]);
  Widget logPage()=>shell('Logs','Live output from the Dana process.',[Expanded(child:card(SelectableText(logs.text.isEmpty?'No logs yet.':logs.text,style:const TextStyle(fontFamily:'monospace',fontSize:12)))]);
  Widget stat(String label,String value,IconData icon)=>SizedBox(width:220,child:card(Column(crossAxisAlignment:CrossAxisAlignment.start,children:[Icon(icon,color:const Color(0xFF8AA9FF)),const SizedBox(height:18),Text(label,style:const TextStyle(color:Colors.white54)),const SizedBox(height:6),Text(value,style:const TextStyle(fontSize:20,fontWeight:FontWeight.w700))])));
  Widget card(Widget child)=>Container(padding:const EdgeInsets.all(20),decoration:BoxDecoration(color:const Color(0xFF121A2C),borderRadius:BorderRadius.circular(22),border:Border.all(color:Colors.white10)),child:child);
}
