PUSHD ..\..
java -jar target\dist\JSCover-all.jar -ws --proxy --port=3128 --report-dir=target/jscover-proxy
POPD