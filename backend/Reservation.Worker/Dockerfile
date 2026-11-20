FROM mcr.microsoft.com/dotnet/sdk:10.0 AS build
WORKDIR /src
COPY backend/Library.Core/Library.Core.csproj backend/Library.Core/
COPY backend/Reservation.Worker/Reservation.Worker.csproj backend/Reservation.Worker/
RUN dotnet restore backend/Reservation.Worker/Reservation.Worker.csproj
COPY backend/Library.Core/ backend/Library.Core/
COPY backend/Reservation.Worker/ backend/Reservation.Worker/
RUN dotnet publish backend/Reservation.Worker/Reservation.Worker.csproj -c Release -o /app/publish --no-restore

FROM mcr.microsoft.com/dotnet/runtime:10.0
WORKDIR /app
COPY --from=build /app/publish .
ENTRYPOINT ["dotnet", "Reservation.Worker.dll"]