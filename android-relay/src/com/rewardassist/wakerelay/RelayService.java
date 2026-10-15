package com.rewardassist.wakerelay;
import android.app.*;
import android.content.*;
import android.os.*;
import android.net.*;
import org.json.JSONObject;
import java.net.*;
import java.util.concurrent.*;
public class RelayService extends Service {
  private ScheduledExecutorService worker;
  private PowerManager.WakeLock pluggedLock;
  private volatile boolean stopping;
  private final BroadcastReceiver powerChange=new BroadcastReceiver(){public void onReceive(Context c,Intent i){updatePower(i);}};
  public void onCreate(){super.onCreate();pluggedLock=getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"RewardAssist:PluggedRelay");pluggedLock.setReferenceCounted(false);registerReceiver(powerChange,new IntentFilter(Intent.ACTION_BATTERY_CHANGED));}
  private synchronized void updatePower(Intent battery){
    boolean plugged=battery!=null&&battery.getIntExtra(BatteryManager.EXTRA_PLUGGED,0)!=0;
    boolean enabled=getSharedPreferences("relay",0).getBoolean("enabled",false);
    if(plugged&&enabled&&!stopping){pluggedLock.acquire(600000);}
    else if(pluggedLock.isHeld())pluggedLock.release();
    getSharedPreferences("relay",0).edit().putBoolean("plugged",plugged).apply();
  }
  private void safePoll(){
    try {if(!stopping&&getSharedPreferences("relay",0).getBoolean("enabled",false)){updatePower(registerReceiver(null,new IntentFilter(Intent.ACTION_BATTERY_CHANGED)));poll();}}
    catch(RuntimeException error){status("Relay check failed ("+error.getClass().getSimpleName()+"). Retrying automatically.");}
  }
  private static final String BASE="https://rewards-assistant-api.mrgobeast.workers.dev/api/wake/tablet/";
  public IBinder onBind(Intent i){return null;}
  private void status(String value){getSharedPreferences("relay",0).edit().putString("status",value).apply();}
  public int onStartCommand(Intent intent,int flags,int id){
    if(!getSharedPreferences("relay",0).getBoolean("enabled",false)){stopSelf();return START_NOT_STICKY;}
    stopping=false;
    getSharedPreferences("relay",0).edit().putLong("service_started",System.currentTimeMillis()).apply();
    NotificationManager manager=getSystemService(NotificationManager.class);
    manager.createNotificationChannel(new NotificationChannel("relay","Computer wake relay",NotificationManager.IMPORTANCE_LOW));
    PendingIntent open=PendingIntent.getActivity(this,0,new Intent(this,MainActivity.class),PendingIntent.FLAG_IMMUTABLE);
    startForeground(1,new Notification.Builder(this,"relay").setSmallIcon(android.R.drawable.ic_lock_idle_charging).setContentTitle("Reward Assist wake relay").setContentText("Listening for your paired computer. Tap to stop or configure.").setContentIntent(open).setOngoing(true).build());
    if(worker==null){worker=Executors.newSingleThreadScheduledExecutor();worker.scheduleWithFixedDelay(this::safePoll,0,20,TimeUnit.SECONDS);}
    return START_STICKY;
  }
  private JSONObject call(String route,JSONObject body) throws Exception {
    HttpURLConnection connection=(HttpURLConnection)new URL(BASE+route).openConnection();
    connection.setInstanceFollowRedirects(false);connection.setConnectTimeout(8000);connection.setReadTimeout(8000);
    connection.setRequestMethod("POST");connection.setDoOutput(true);connection.setRequestProperty("Content-Type","application/json");
    connection.setRequestProperty("Authorization","Bearer "+getSharedPreferences("relay",0).getString("token",""));
    try {
      try(java.io.OutputStream out=connection.getOutputStream()){out.write(body.toString().getBytes("UTF-8"));}
      int code=connection.getResponseCode();
      if(code==401){getSharedPreferences("relay",0).edit().putBoolean("enabled",false).apply();stopSelf();throw new Exception("Pairing expired or removed. Pair again on iPhone.");}
      if(code==404)throw new Exception("Wake service is not deployed yet.");
      if(code!=200)throw new Exception("Wake service unavailable ("+code+"). Retrying.");
      try(java.io.InputStream in=connection.getInputStream();java.io.ByteArrayOutputStream out=new java.io.ByteArrayOutputStream()){
        byte[] buffer=new byte[1024];int n;while((n=in.read(buffer))!=-1){if(out.size()+n>8192)throw new Exception("Invalid server response.");out.write(buffer,0,n);}return new JSONObject(out.toString("UTF-8"));
      }
    }finally{connection.disconnect();}
  }
  private void poll(){
    PowerManager.WakeLock lock=getSystemService(PowerManager.class).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"RewardAssist:WakeRelay");
    try {
      lock.acquire(60000);
      getSharedPreferences("relay",0).edit().putLong("last_attempt",System.currentTimeMillis()).apply();
      ConnectivityManager cm=getSystemService(ConnectivityManager.class);Network wifi=null;
      for(Network net:cm.getAllNetworks()){NetworkCapabilities caps=cm.getNetworkCapabilities(net);if(caps!=null&&caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI)&&!caps.hasTransport(NetworkCapabilities.TRANSPORT_VPN)){wifi=net;break;}}
      if(wifi==null){status("Connect this tablet to your home Wi-Fi.");return;}
      JSONObject response=call("poll",new JSONObject());String id=response.optString("request","");
      getSharedPreferences("relay",0).edit().putLong("last_success",System.currentTimeMillis()).apply();
      if(stopping||!getSharedPreferences("relay",0).getBoolean("enabled",false))return;
      if(id.isEmpty()||id.equals("null")){status("Online · checked "+java.text.DateFormat.getTimeInstance().format(new java.util.Date()));return;}
      if(!id.matches("(?i)[a-f0-9-]{36}"))throw new Exception("Invalid wake request.");
      String result="failed";
      try {
        byte[] packet=WakePacket.create(getSharedPreferences("relay",0).getString("mac",""));
        LinkProperties props=cm.getLinkProperties(wifi);boolean sent=false;
        if(props!=null)for(LinkAddress address:props.getLinkAddresses()){
          if(!(address.getAddress() instanceof Inet4Address))continue;
          int prefix=address.getPrefixLength();if(prefix<1||prefix>30)continue;
          byte[] ip=address.getAddress().getAddress();int raw=0;for(byte b:ip)raw=(raw<<8)|(b&255);
          int broadcast=raw|(-1>>>prefix);byte[] target={(byte)(broadcast>>>24),(byte)(broadcast>>>16),(byte)(broadcast>>>8),(byte)broadcast};
          try(DatagramSocket socket=new DatagramSocket()){wifi.bindSocket(socket);socket.setBroadcast(true);socket.send(new DatagramPacket(packet,packet.length,InetAddress.getByAddress(target),9));sent=true;}
        }
        if(!sent)throw new Exception("No home Wi-Fi broadcast address available.");result="sent";
      }catch(Exception e){status("Wake signal failed. Check home Wi-Fi and PC MAC address.");}
      call("ack",new JSONObject().put("id",id).put("result",result));
      status(result.equals("sent")?"Wake signal sent. Check the PC's online status on iPhone.":"Could not send wake signal.");
    }catch(Exception e){status(e.getMessage()==null?"Connection interrupted. Retrying.":e.getMessage());}
    finally{if(lock.isHeld())lock.release();}
  }
  public void onDestroy(){stopping=true;if(worker!=null)worker.shutdownNow();worker=null;unregisterReceiver(powerChange);synchronized(this){if(pluggedLock!=null&&pluggedLock.isHeld())pluggedLock.release();}getSharedPreferences("relay",0).edit().putLong("service_stopped",System.currentTimeMillis()).apply();super.onDestroy();}
}
